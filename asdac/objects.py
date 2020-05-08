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


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Type:
    name: str


# all variables are local variables for now.
# note that there is code that uses copy.copy() with Variable objects
@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Variable:
    name: str
    type: Type
    kind: VariableKind
    definition_location: typing.Optional[Location]


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Function:
    name: str
    argvars: typing.List[Variable]
    returntype: typing.Optional[Type]
    kind: FunctionKind
    definition_location: typing.Optional[Location]
    is_main: bool = False

    def get_string(self) -> str:
        return '%s(%s)' % (self.name, ', '.join(
            var.type.name + ' ' + var.name
            for var in self.argvars
        ))
            

BUILTIN_TYPES = collections.OrderedDict((tybe.name, tybe) for tybe in [
    Type('Object'),
    Type('Str'),
    Type('Int'),
    Type('Bool'),
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

BUILTIN_FUNCS = collections.OrderedDict((func.name, func) for func in [
    Function(
        name='print',
        argvars=[
            Variable(
                name='message',
                type=BUILTIN_TYPES['Str'],
                kind=VariableKind.LOCAL,
                definition_location=None,
            ),
        ],
        returntype=None,
        kind=FunctionKind.BUILTIN,
        definition_location=None,
    ),
])
