"""Objects and other related things.

Even though types, generic types and generic variables are not objects in asda,
they are here as well.
"""

import collections
import copy
import typing

from asdac import common


# non-settable attributes are aka read-only
Attribute = collections.namedtuple('Attribute', ['tybe', 'settable'])


class Type:

    # if you want the name to change when the class is mutated, you can pass
    # None for __init__'s name and override the name property
    def __init__(self, name: str):
        self.name = name

    def __repr__(self) -> str:
        return '<%s type %r>' % (__name__, self.name)


BUILTIN_TYPES = collections.OrderedDict([
    ('Object', Type('Object')),
    ('Str', Type('Str')),
    ('Int', Type('Int')),
    ('Bool', Type('Bool')),
])

BUILTIN_VARS = collections.OrderedDict([
    ('TRUE', BUILTIN_TYPES['Bool']),
    ('FALSE', BUILTIN_TYPES['Bool']),
])

# keys are name strings, values are (argtypes, returntype) pairs
BUILTIN_FUNCS = collections.OrderedDict([
    ('print', ([BUILTIN_TYPES['Str']], None)),
])
