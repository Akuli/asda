"""Objects and other related things.

Even though types, generic types and generic variables are not objects in asda,
they are here as well.
"""

import collections
import enum
import typing

import attr

from asdac.common import Location


class VariableKind(enum.Enum):
    BUILTIN = 0
    LOCAL = 1


class FunctionKind(enum.Enum):
    BUILTIN = 0
    FILE = 1


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Type:
    name: str


# all variables are local variables for now.
# note that there is code that uses copy.copy() with Variable objects
@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Variable:
    name: str
    type: Type
    kind: VariableKind
    definition_location: typing.Optional[Location]


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True, repr=False)
class Function:
    name: str
    argvars: typing.List[Variable]
    returntype: typing.Optional[Type]
    kind: FunctionKind
    definition_location: typing.Optional[Location]
    is_main: bool = False

    def __repr__(self):
        return f'<{__name__}.Function {repr(self.name)}>'

    def get_string(self) -> str:
        return '%s(%s)' % (self.name, ', '.join(
            var.type.name + ' ' + var.name
            for var in self.argvars
        ))


BUILTIN_TYPES = collections.OrderedDict((tybe.name, tybe) for tybe in [
    Type('Str'),
    Type('Int'),
    Type('Bool'),
    Type('Object'),
])

BUILTIN_VARS = collections.OrderedDict((var.name, var) for var in [
    Variable(
        name='TRUE',
        type=BUILTIN_TYPES['Bool'],
        kind=VariableKind.BUILTIN,
        definition_location=None,
    ),
    Variable(
        name='FALSE',
        type=BUILTIN_TYPES['Bool'],
        kind=VariableKind.BUILTIN,
        definition_location=None,
    ),
])


def _argvars(magic_string: str) -> typing.List[Variable]:
    return [
        Variable(
            name=argname,
            type=BUILTIN_TYPES[typename],
            kind=VariableKind.LOCAL,
            definition_location=None,
        )
        for typename, argname in map(str.split, magic_string.split(','))
    ]


_boilerplate: typing.Dict[str, typing.Any] = dict(
    kind=FunctionKind.BUILTIN,
    definition_location=None,
)

BUILTIN_FUNCS = {func.name: func for func in [
    Function(
        name='print',
        argvars=_argvars('Str message'),
        returntype=None,
        **_boilerplate,
    ),

    Function(
        name='not',
        argvars=_argvars('Bool b'),
        returntype=BUILTIN_TYPES['Bool'],
        **_boilerplate,
    ),

    Function(
        name='Str+Str',
        argvars=_argvars('Str a, Str b'),
        returntype=BUILTIN_TYPES['Str'],
        **_boilerplate,
    ),
    Function(
        name='Int+Int',
        argvars=_argvars('Int a, Int b'),
        returntype=BUILTIN_TYPES['Int'],
        **_boilerplate,
    ),
    Function(
        name='Int-Int',
        argvars=_argvars('Int a, Int b'),
        returntype=BUILTIN_TYPES['Int'],
        **_boilerplate,
    ),
    Function(
        name='Int*Int',
        argvars=_argvars('Int a, Int b'),
        returntype=BUILTIN_TYPES['Int'],
        **_boilerplate,
    ),
    Function(
        name='-Int',
        argvars=_argvars('Int a'),
        returntype=BUILTIN_TYPES['Int'],
        **_boilerplate,
    ),

    Function(
        name='Int==Int',
        argvars=_argvars('Int a, Int b'),
        returntype=BUILTIN_TYPES['Bool'],
        **_boilerplate,
    ),
    Function(
        name='Str==Str',
        argvars=_argvars('Str a, Str b'),
        returntype=BUILTIN_TYPES['Bool'],
        **_boilerplate,
    ),
    Function(
        name='Bool==Bool',
        argvars=_argvars('Bool a, Bool b'),
        returntype=BUILTIN_TYPES['Bool'],
        **_boilerplate,
    ),
    Function(
        name='int_to_string',
        argvars=_argvars('Int i'),
        returntype=BUILTIN_TYPES['Str'],
        **_boilerplate,
    ),
]}

BUILTIN_PREFIX_OPERATORS = {
    ('-', BUILTIN_TYPES['Int']): BUILTIN_FUNCS['-Int'],
}

BUILTIN_BINARY_OPERATORS = {
    (BUILTIN_TYPES[t1], op, BUILTIN_TYPES[t2]): BUILTIN_FUNCS[t1 + op + t2]
    for t1, op, t2 in [
        ('Str', '+', 'Str'),
        ('Int', '+', 'Int'),
        ('Int', '-', 'Int'),
        ('Int', '*', 'Int'),

        ('Str', '==', 'Str'),
        ('Int', '==', 'Int'),
        ('Bool', '==', 'Bool'),
    ]
}
