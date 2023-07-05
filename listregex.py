from typing import Sequence, TypeVar, Any, Callable, Iterator, Generic, Tuple, Dict, no_type_check

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
    def n_remaining(self) -> int:
        return len(self.items) - self.end

    @property
    def matched(self) -> Sequence[Item]:
        """
        List of matched items (potentially empty for patterns with `optional`
        and `lookahead`).
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
        return f'Match({repr(self.matched)})'

LeafPatternType = Item | Callable[[Match[Item]], bool | int | Iterator[Match[Item]]]
PatternType = LeafPatternType[Item] | Sequence[LeafPatternType[Item]]

def _match_sequence(pattern: Sequence[LeafPatternType[Item]], match: Match[Item]) -> Iterator[Match[Item]]:
    """
    Returns the match for a pattern that is a sequence of sub-patterns.
    """
    matches = [match]
    for subpattern in pattern:
        matches = [next_match for match in matches for next_match in _next_match(subpattern, match)]
        if not matches: return
    yield from matches

def _next_match(pattern: PatternType[Item], match: Match[Item]) -> Iterator[Match[Item]]:
    """
    Test a single pattern against the items after the current match.
    """
    if callable(pattern):
        try:
            result = pattern(match)
        except NoMoreItems:
            # Removes the need to sprinkle "m.has_next" all over custom functions.
            result = 0

        if result == 0:
            return
        elif isinstance(result, Iterator):
            yield from result
        else:
            yield match.advance(result)
    else:
        if isinstance(pattern, (tuple, list)):
            # A pattern that looks like a list could either be a literal list,
            # in case the items themselves are lists, or a sequence of patterns.
            # Try matching it as a sequence of patterns first, and return that
            # if it works.
            yield from _match_sequence(pattern, match)
        if match.has_next and match.next == pattern:
            yield match.advance(1)

#######################
# Pattern combinators #
#######################

def any() -> PatternType[Item]:
    """" Matches any single item. """
    return lambda match: True

def start() -> PatternType[Item]:
    """ Matches the start of the item list. """
    return lambda match: match.end == 0

def end() -> PatternType[Item]:
    """ Matches the end of the item list. """
    return lambda match: match.end == len(match.items)

def either(*patterns: PatternType[Item]) -> PatternType[Item]:
    """ Returns the first successful match, if any. """
    def wrapper(old_match: Match[Item]) -> Iterator[Match]:
        for pattern in patterns:
            yield from _next_match(pattern, old_match)
    return wrapper

def both(*patterns: PatternType[Item]) -> PatternType[Item]:
    """ Only matches if all patterns match. Returns the longest match. """
    def wrapper(old_match: Match[Item]) -> Iterator[Match]:
        matches_by_pattern = [set(m.end for m in _next_match(pattern, old_match)) for pattern in patterns]
        for end in set.intersection(*matches_by_pattern):
            yield Match(old_match.items, old_match.start, end)
    return wrapper	

def lookahead(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Tests the given pattern without extending the current match. """
    def wrapper(old_match: Match[Item]) -> Iterator[Match]:
        for new_match in _next_match(pattern, old_match):
            yield old_match
            return
    return wrapper

def optional(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Applies the given pattern, skipping it if it fails. """
    def wrapper(old_match: Match[Item]) -> Iterator[Match]:
        yield old_match
        yield from _next_match(pattern, old_match)
    return wrapper

def repeat(pattern: PatternType[Item], min_n: int = 1, max_n: int | None = None) -> PatternType[Item]:
    """
    Repeats the pattern as many times as it'll match (greedy), if the number
    of repetitions is at least `min_n` (default 1) and at most below `max_n`
    (default unlimited).
    """
    def wrapper(match: Match[Item]) -> Iterator[Match]:
        nonlocal max_n
        max_n = len(match.items) if max_n is None else max_n
        matches = [match]
        for n in range(min(len(match.items), max_n)):
            matches = [next_match for match in matches for next_match in _next_match(pattern, match)]
            if min_n <= n <= max_n:
                yield from matches
    return wrapper

def one_or_more(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Matches the given pattern one or more times (greedy). """
    return repeat(pattern, min_n=1)

def zero_or_more(pattern: PatternType[Item]) -> PatternType[Item]:
    """ Matches the given pattern zero or more times (greedy). """
    return repeat(pattern, min_n=0)

def negate(pattern: PatternType[Item]) -> PatternType[Item]:
    """
    Matches any single item except if it would have matched the given pattern.
    """
    def wrapper(match: Match[Item]) -> Iterator[Match]:
        for _ in _next_match(pattern, match):
            return
        yield match.advance(1)
    return wrapper

def matching_pair(open: PatternType[Item], close: PatternType[Item]) -> PatternType[Item]:
    """ Matches `open` until the next balanced pair of `close`. """
    def wrapper(old_match: Match[Item]) -> Iterator[Match]:
        matches_and_depths = [(match, 1) for match in _next_match(open, old_match)]
        while matches_and_depths:
            match, depth = matches_and_depths.pop()
            if new_matches := list(_next_match(open, match)):
                depth += 1
            elif new_matches := list(_next_match(close, match)):
                depth -= 1
                if depth == 0:
                    yield from new_matches
                    continue
            elif not match.has_next:
                continue
            else:
                new_matches = [match.advance(1)]

            matches_and_depths.extend((match, depth) for match in new_matches)
    return wrapper

def backreference(n: int = 0) -> PatternType[Item]:
    """ Matches an element identical to the n-th matched item (default: first). """
    def wrapper(match: Match[Item]):
        return match[n] == match.next
    return wrapper

############
# Matchers #
############

def scan(patterns: Dict[str, PatternType[Item]], items: Sequence[Item]) -> Iterator[Tuple[str, Match[Item]]]:
    match = Match(items, 0, 0)
    while match.end < len(items):
        matches = [(name, new_match) for name, pattern in patterns.items() for new_match in _next_match(pattern, match)]
        if not matches: return
        name, new_match = matches[0]
        yield name, Match(items, match.end, new_match.end)
        match = new_match

def match(pattern: PatternType[Item], items: Sequence[Item]) -> Match[Item] | None:
    """
    Returns the longest match from the beginning of the items list. Use
    `fullmatch` to guarantee that the full list has been matched.
    """
    return next(_next_match(pattern, Match(items, 0, 0)))

def fullmatch(pattern: PatternType[Item], items: Sequence[Item]) -> Match[Item] | None:
    """
    Tries to match all items with the given pattern.
    """
    for match in _next_match(pattern, Match(items, 0, 0)):
        if not match.has_next:
            return match
    return None

def searchall(pattern: PatternType[Item], items: Sequence[Item]) -> Iterator[Match[Item]]:
    """
    Returns all non-overlapping matches from the list of items.
    """
    start = 0
    while start < len(items):
        match = search(pattern, items, start=start)
        if not match:
            return
        yield match
        start = match.end

def findall(pattern: PatternType[Item], items: Sequence[Item]) -> Iterator[Sequence[Item]]:
    """ Returns all non-overlapping matched items from the list of items. """
    return (match.matched for match in searchall(pattern, items))

def search(pattern: PatternType[Item], items: Sequence[Item], start: int = 0) -> Match[Item] | None:
    """
    Returns the first match from the list of items.
    """
    for i in range(start, len(items)):
        for match in _next_match(pattern, Match(items, i, i)):
            return match
    return None

def sub(pattern: PatternType[Item], replacement: Sequence[Item], items: Sequence[Item], count: int = 0) -> Sequence[Item]:
    """
    Replaces every match of `pattern` in `items` with `replacement`, up to
    `count` times (or as many times as possible if count is 0).
    """
    new_items, n_subs = subn(pattern, replacement, items)
    return new_items

def subn(pattern: PatternType[Item], replacement: Sequence[Item], items: Sequence[Item], count: int = 0) -> Tuple[Sequence[Item], int]:
    """
    Replaces every match of `pattern` in `items` with `replacement`, up to
    `count` times (or as many times as possible if count is 0). Returns
    the items list with replacements applied and number of replacements made.
    """
    items_copy = list(items)
    matches = list(searchall(pattern, items))
    if count > 0:
        matches = matches[:count]
    for match in reversed(matches):
        if callable(replacement):
            new_value = replacement(match)
        else:
            new_value = replacement
        items_copy[match.start:match.end] = new_value
    return items_copy, len(matches)

def split(pattern: PatternType[Item], items: Sequence[Item], maxsplit: int = 0) -> Sequence[Sequence[Item]]:
    """
    Returns slices of `items`, split on every match of `pattern`, up to
    `maxsplit` times (unless zero). The matched items themselves are not
    included.
    """
    matches = list(searchall(pattern, items))
    if maxsplit > 0:
        matches = matches[:maxsplit]
    last_end = 0
    result = []
    for match in matches:
        result.append(items[last_end:match.start])
        last_end = match.end
    result.append(items[last_end:])
    return result

if __name__ == '__main__':
    @no_type_check
    def tests():
        assert search([1, lookahead(2)], [1, 2, 3]).matched == [1]
        assert list(findall(either(1, 2), [1, 2, 3])) == [[1], [2]]
        assert fullmatch([1, 2, 3], [1, 2, 3])
        assert fullmatch([1, 2, optional(2), 3], [1, 2, 3])
        assert fullmatch([1, repeat(1), 1], [1, 1, 1, 1])
        assert search([2, 3], [1, 2, 3]).start == 1
        assert fullmatch([1, any(), 3], [1, 2, 3])
        assert search([one_or_more(lambda m: 0 < m.next < 3)], [0, 1, 2, 3]).matched == [1, 2]
        assert list(findall(lambda m: 0 < m.next < 3, [0, 1, 2, 3])) == [[1], [2]]
        assert search([1, repeat([2, optional(3)])], [0, 1, 2, 3, 2, 4]).matched == [1, 2, 3, 2]
        assert search(repeat([1, 2]), [0, 1, 2, 1, 2, 3, 2, 4]).matched == [1, 2, 1, 2]
        assert sub([1, 2], [], [0, 1, 2, 1, 2, 3]) == [0, 3]
        assert search(matching_pair('(', ')'), 'ab(c(d()e)f)').matched == '(c(d()e)f)'
        assert search(matching_pair('(', ')'), 'ab(c(d()e)f').matched == '(d()e)'
        assert search(matching_pair('(', ')'), 'ab(c(d(ef') is None
        assert fullmatch([lambda m: m.next%2==0, any(), backreference()], [4, 1, 4])
        assert search(both(either('a', repeat('b')), either(['b', 'b'], 'c')), 'aabbc').matched == 'bb'

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