"""Objects and other related things.

Even though types, generic types and generic variables are not objects in asda,
they are here as well.
"""

import collections
import copy

from asdac import common


# non-settable attributes are aka read-only
Attribute = collections.namedtuple('Attribute', ['tybe', 'settable'])

#GenericInfo = collections.namedtuple('GenericInfo', ['generic_obj', 'types'])


class Type:

    # if you want the name to change when the class is mutated, you can pass
    # None for __init__'s name and override the name property
    def __init__(self, name: str):
        self.name = name

    def __repr__(self):
        return '<%s type %r>' % (_name__, self.name)


def _fill_builtin_types_ordered_dict():
    def create_and_add(name):
        BUILTIN_TYPES[name] = Type(name)

    create_and_add('Object')
    create_and_add('Str')
    create_and_add('Int')
    create_and_add('Bool')


BUILTIN_TYPES = collections.OrderedDict()
_fill_builtin_types_ordered_dict()

BUILTIN_VARS = collections.OrderedDict([
    ('TRUE', BUILTIN_TYPES['Bool']),
    ('FALSE', BUILTIN_TYPES['Bool']),
])

# keys are name strings, values are (argtypes, returntype) pairs
BUILTIN_FUNCS = collections.OrderedDict([
    ('print', ([BUILTIN_TYPES['Str']], None)),
])


# feels nice and evil to create a class with just one method >xD MUHAHAHA ...
class UserDefinedClass(Type):

    def __init__(self, name, attr_arg_types: collections.OrderedDict):
        super().__init__(name, BUILTIN_TYPES['Object'])

        assert not self.attributes
        self.attributes.update(
            (name, Attribute(tybe, True))
            for name, tybe in attr_arg_types.items()
        )

        self.constructor_argtypes = list(attr_arg_types.values())
