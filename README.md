# objregex

`objregex` implements the same functions as Python's stdlib `re` module, but instead of operating only on strings, it operates on lists of arbitrary objects.

Currently uses a naive regex engine, with greedy operators and no backtrack.

```python
from objregex import *

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
