# listregex

`listregex` implements the same functions as Python's stdlib `re` module (and a few more), but instead of operating only on strings, it operates on lists of arbitrary objects. If you've found yourself writing awkward code to extract subsequences from a list, and thought to yourself "this would be a tiny regex if my list was a string", then this is the library.

This is not a high-speed regex engine, as it currently uses naive backtracking in pure Python. On the other hand, there's greater flexibility in the patterns allowed, and even a mechanism for arbitrary tests.

Patterns can be:

- A single literal value. Example: `search(pattern=1, items=[1, 2])` matches `[1]`.
- A list/tuple of patterns, where the sub-patterns are matched sequentially. Example: `search([1, 2], [0, 1, 2])` matches `[1, 2]`.
- A value from a helper function, such as `optional(pattern)`, `zero_or_more(pattern)`, `end()`, etc. Example: `findall(repeat(1), my_list)` finds all sequences of 1's.
- Any combination of the above. Example: `search(pattern=[1, repeat(negate(3)), 1], items=[0, 2, 1, 3, 1, 2, 1, 0])` matches `[1, 2, 1]`.
- A function that takes one parameter, the current match, and returns the number of following items that should be added to be match (note that `True == 1` and `False == 0`). Returning 0 means no match and the engine backtracks. Examples:
    - `lambda m: 2` blindly accepts the next two items, such that `findall(lambda m: 2, items)` returns the items divided in pairs.
    - `lambda m: m.next % 2 == 0` checks if the next item is even, and if so, extends the match to include it.
    - `lambda m: m.items.count(m.next) > 1` matches all items that occur more than once.
    - `lambda m: m[0] > m.next` compares the first item of the current match with the next.

```python
from listregex import *

# Matches 1 and 3, optionally with a 2 between them:
fullmatch([1, optional(2), 3], [1, 3])
# Match(1, 3)

# A sequence of 1 or more items between 0 and 3:
search(repeat(lambda m: 0 < m.next <= 3), [0, 1, 2, 3, 4])
# Match(1, 2, 3)

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
# Find suspicious logins by looking at quick country switches:
pattern = [
    # Start from any login...
    any(),
    
    # Followed by one or more logins at a different country...
    repeat(lambda m: m[0].country != m.next.country), 
    
    # Followed by a login at the original country within 2 days.
    lambda m: m.next.date - m[0].date < timedelta(days=2), 
]
search(pattern, logins)[1].country
# 'Russia'

# Collapses repeated elements.
sub([any(), zero_or_more(lambda m: m.next == m[0])], lambda m: [m[0]], [1, 2, 3, 3, 4, 5, 5])
# [1, 2, 3, 4, 5]

# Parses a binary array where elements are encoded as [length, *values].
findall(lambda m: int(m[0])+1, b'\x00\x01\x55\x02\x66\x66\x00')
# [b'\x00', b'\x01\x55', b'\x02\x66\x66', b'\x00']

# Finds all items that are bigger than the next, or at the `end` of the list.
# Uses `lookahead` to allow the next item to also be matched.
findall([any(), either(end(), lookahead(lambda m: m[0] > m.next))], [1, 2, 1, 3, 2, 4, 3, 1])
# [[2], [3], [4], [3], [1]]
```
