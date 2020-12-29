class NoMoreItems(Exception):
    """
    Error raised when calling "match.next" at no more items are available.
    """

class Match:
    """
    A subsequence of items that match a certain pattern.
    """
    def __init__(self, items, start, end):
        self.items = items
        self.start = start
        self.end = end

    def __getitem__(self, n):
        """
        Shortcut to the n-th matched item.
        """
        return self.items[self.start + n]

    @property
    def has_next(self):
        """
        Returns True if there are more items after the matched ones.
        """
        return self.end < len(self.items)

    @property
    def next(self):
        """
        Returns the next item after the matched ones, or raises NoMoreItems.
        """
        if self.end >= len(self.items):
            raise NoMoreItems()
        return self.items[self.end]

    @property
    def rest(self):
        """
        List of all items after the matched ones.
        """
        return self.items[self.end:]

    @property
    def matched(self):
        """
        List of matched items (potentially empty for patterns with optional
        matchers).
        """
        return self.items[self.start:self.end]

    def advance(self, n):
        """
        Returns a new match with the same matched items plus the next n items.
        """
        return Match(self.items, self.start, self.end + n)

    def __equals__(self, other):
        return isinstance(other, Match) and self.items == other.items and self.start == other.start and self.end == other.end

    def __repr__(self):
        return f'Match({", ".join(map(str, self.matched))})'

def _test_one(next_matcher, match):
    """
    Test a single matcher against the items after the current match.
    """
    if not callable(next_matcher):
        return match.advance(1) if match.has_next and match.next == next_matcher else None

    try:
        result = next_matcher(match)
    except NoMoreItems:
        # Removes the need to sprinkle "m.has_next" all over custom matchers.
        result = None

    if isinstance(result, Match):
        return result
    elif result == 0 or result is None:
        return None
    else:
        return match.advance(result)

def _general_match(matchers, items, start=0):
    """
    Test a sequence of matchers against a list of items, with an optional start
    index offset.
    """
    match = Match(items, start, start)
    for matcher in matchers:
        match = _test_one(matcher, match)
        if match is None: break
    return match

############################
# Start of user functions. #
############################

def any():
    """"Matches any single item. """
    return lambda match: True

def start():
    """ Matches the start of the items list. """
    return lambda match: match.end == 0

def end():
    """ Matches the end of the items list. """
    return lambda match: match.end == len(match.items)

#def either(*options):
#    def wrapper(match, items):
#        for option in options:
#            result = _test_one(option, match, items)

def optional(matcher):
    """ Applies the given matcher, skipping it if it fails. """
    def wrapper(old_match):
        new_match = _test_one(matcher, old_match)
        return old_match if new_match is None else new_match
    return wrapper

def repeat(matcher, min_n=1, max_n=None):
    """
    Repeats the matcher as many times as it'll match (greedy), if the number
    of repetitions if above `min_n` and below `max_n` (if not None)
    """
    def wrapper(match):
        for _ in range(min_n):
            match = _test_one(matcher, match)
            if match is None:
                return None
        for _ in range(max_n - min_n if max_n is not None else len(match.items) - match.end):
            new_match = _test_one(matcher, match)
            if new_match is None or new_match == match:
                return match
            match = new_match
        return match
    return wrapper

def one_or_more(matcher):
    """ Matches the given matcher one or more times (greedy). """
    return repeat(matcher, min_n=1)

def zero_or_more(matcher):
    """ Matches the given matcher zero or more times (greedy). """
    return repeat(matcher, min_n=0)

def fullmatch(matchers, items):
    """
    Tries to match all items with the given matchers.
    """
    match = _general_match(matchers, items)
    return match if match and not match.has_next else None

def findall(matchers, items):
    """
    Returns all non-overlapping matches from the list of items.
    """
    start = 0
    while start < len(items):
        match = _general_match(matchers, items, start=start)
        if match:
            yield match
            start = match.end
        else:
            start += 1

def search(matchers, items):
    """
    Returns the first match from the list of items.
    """
    try:
        return next(findall(matchers, items))
    except StopIteration:
        return None

if __name__ == '__main__':
    assert fullmatch([1, 2, 3], [1, 2, 3]).end == 3
    assert search([2, 3], [1, 2, 3]).start == 1
    assert fullmatch([1, any(), 3], [1, 2, 3])
    assert search([one_or_more(lambda m: 0 < m.next < 3)], [0, 1, 2, 3]).matched == [1, 2]

    from datetime import date, timedelta
    from collections import namedtuple
    Login = namedtuple('Login', 'country date')
    logins = [
        Login('Germany', date(2020, 1, 1)),
        Login('Belgium', date(2020, 1, 2)),
        Login('Germany', date(2020, 3, 1)),
        Login('Germany', date(2020, 3, 2)),
        Login('Russia', date(2020, 3, 2)),
        Login('Russia', date(2020, 3, 2)),
        Login('Germany', date(2020, 3, 3)),
    ]
    pattern = [
        any(),
        repeat(lambda m: m[0].country != m.next.country),
        lambda m: m.next.date - m[0].date < timedelta(days=2),
    ]
    assert search(pattern, logins)[1].country == 'Russia'