from typing import Sequence, TypeVar, Any, Optional, Callable, Iterator, Union, Generic, no_type_check

class NoMoreItems(Exception):
    """
    Error raised when calling "match.next" at no more items are available.
    """

Item = TypeVar("Item")
class Match(Generic[Item]):
    """
    A subsequence of items that match a certain pattern.
    """
    def __init__(self, items: Sequence[Item], start: int = 0, end: int = 0) -> None:
        self.items = items
        self.start = start
        self.end = end

    def __getitem__(self, n: int) -> Item:
        """
        Shortcut to the n-th matched item.
        """
        return self.items[self.start + n]

    @property
    def has_next(self) -> bool:
        """
        Returns True if there are more items after the matched ones.
        """
        return self.end < len(self.items)

    @property
    def next(self) -> Item:
        """
        Returns the next item after the matched ones, or raises NoMoreItems.
        """
        if self.end >= len(self.items):
            raise NoMoreItems()
        return self.items[self.end]

    @property
    def rest(self) -> Sequence[Item]:
        """
        List of all items after the matched ones.
        """
        return self.items[self.end:]

    @property
    def matched(self) -> Sequence[Item]:
        """
        List of matched items (potentially empty for patterns with optional
        patterns).
        """
        return self.items[self.start:self.end]

    def advance(self, n: int) -> 'Match':
        """
        Returns a new match with the same matched items plus the next n items.
        """
        return Match(self.items, self.start, self.end + n)

    def __equals__(self, other:Any) -> bool:
        return isinstance(other, Match) and self.items == other.items and self.start == other.start and self.end == other.end

    def __repr__(self) -> str:
        return f'Match({", ".join(str(item) for item in self.matched)})'

LeafPatternType = Union[Item, Callable[[Match[Item]], Union[bool, int, None, Match[Item]]]]
PatternType = Union[LeafPatternType[Item], Sequence[LeafPatternType[Item]]]

def _match_sequence(pattern: Sequence[LeafPatternType[Item]], match: Match[Item]) -> Optional[Match[Item]]:
    """
    Returns the match for a pattern that is a sequence of sub-patterns.
    """
    for subpattern in pattern:
        new_match = _next_match(subpattern, match)
        if new_match is None: return None
        match = new_match
    return match

def _next_match(pattern: PatternType[Item], match: Match[Item]) -> Optional[Match[Item]]:
    """
    Test a single pattern against the items after the current match.
    """
    if callable(pattern):
        try:
            result = pattern(match)
        except NoMoreItems:
            # Removes the need to sprinkle "m.has_next" all over custom patterns.
            result = None

        if isinstance(result, Match):
            return result
        elif result == 0 or result is None:
            return None
        else:
            return match.advance(result)
    else:
        if isinstance(pattern, (tuple, list)):
            # A pattern that looks like a list could either be a literal list,
            # in case the items themselves are lists, or a sequence of patterns.
            # Try matching it as a sequence of patterns first, and return that
            # if it works.
            result = _match_sequence(pattern, match)
            if result:
                return result
        return match.advance(1) if match.has_next and match.next == pattern else None

#######################
# Pattern combinators #
#######################

def any() -> PatternType[Item]:
    """"Matches any single item. """
    return lambda match: True

def start() -> PatternType[Item]:
    """ Matches the start of the items list. """
    return lambda match: match.end == 0

def end() -> PatternType[Item]:
    """ Matches the end of the items list. """
    return lambda match: match.end == len(match.items)

def either(*patterns: PatternType[Item]) -> PatternType[Item]:
    """ Returns the first successful match, if any. """
    def wrapper(old_match: Match[Item]) -> Optional[Match]:
        for pattern in patterns:
            new_match = _next_match(pattern, old_match)
            if new_match is not None:
                return new_match
        return None
    return wrapper

def lookahead(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Tests the given pattern without extending the current match. """
    def wrapper(old_match: Match[Item]) -> Optional[Match]:
        new_match = _next_match(pattern, old_match)
        return old_match if new_match is not None else None
    return wrapper

def optional(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Applies the given pattern, skipping it if it fails. """
    def wrapper(old_match: Match[Item]) -> Match:
        new_match = _next_match(pattern, old_match)
        return old_match if new_match is None else new_match
    return wrapper

def repeat(pattern: PatternType[Item], min_n: int = 1, max_n: Optional[int] = None) -> PatternType[Item]:
    """
    Repeats the pattern as many times as it'll match (greedy), if the number
    of repetitions if above `min_n` and below `max_n` (if not None)
    """
    def wrapper(match: Match[Item]) -> Optional[Match]:
        for _ in range(min_n):
            new_match = _next_match(pattern, match)
            if new_match is None:
                return None
            match = new_match
        for _ in range(max_n - min_n if max_n is not None else len(match.items) - match.end):
            new_match = _next_match(pattern, match)
            if new_match is None or new_match == match:
                return match
            match = new_match
        return match
    return wrapper

def one_or_more(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Matches the given pattern one or more times (greedy). """
    return repeat(pattern, min_n=1)

def zero_or_more(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Matches the given pattern zero or more times (greedy). """
    return repeat(pattern, min_n=0)

############
# Matchers #
############

def match(patterns: PatternType[Item], items: Sequence[Item]) -> Optional[Match[Item]]:
    """
    Returns the longest match from the beginning of the items list. Use
    `fullmatch` to guarantee that the full list has been matched.
    """
    return _next_match(patterns, Match(items, 0, 0))

def fullmatch(patterns: PatternType[Item], items: Sequence[Item]) -> Optional[Match[Item]]:
    """
    Tries to match all items with the given patterns.
    """
    match = _next_match(patterns, Match(items, 0, 0))
    return match if match and not match.has_next else None

def findall(patterns: PatternType[Item], items: Sequence[Item]) -> Iterator[Sequence[Item]]:
    """
    Returns all non-overlapping matched items from the list of items.
    """
    start = 0
    while start < len(items):
        match = search(patterns, items, start=start)
        if not match:
            return
        yield match.matched
        start = match.end

def search(patterns: PatternType[Item], items: Sequence[Item], start: int = 0) -> Optional[Match[Item]]:
    """
    Returns the first match from the list of items.
    """
    for i in range(start, len(items)):
        match = _next_match(patterns, Match(items, i, i))
        if match:
            return match
    return None

if __name__ == '__main__':
    @no_type_check
    def tests():
        assert search([1, lookahead(2)], [1, 2, 3]).matched == [1]
        assert list(findall(either(1, 2), [1, 2, 3])) == [[1], [2]]
        assert fullmatch([1, 2, 3], [1, 2, 3]).end == 3
        assert search([2, 3], [1, 2, 3]).start == 1
        assert fullmatch([1, any(), 3], [1, 2, 3])
        assert search([one_or_more(lambda m: 0 < m.next < 3)], [0, 1, 2, 3]).matched == [1, 2]
        assert list(findall(lambda m: 0 < m.next < 3, [0, 1, 2, 3])) == [[1], [2]]
        assert search([1, repeat([2, optional(3)])], [0, 1, 2, 3, 2, 4]).matched == [1, 2, 3, 2]
        assert search(repeat([1, 2]), [0, 1, 2, 1, 2, 3, 2, 4]).matched == [1, 2, 1, 2]

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
        print('Test passed.')
    tests()