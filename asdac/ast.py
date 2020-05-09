import collections
import enum
import typing

import attr

from asdac.common import Location
from asdac.objects import Variable, Function, Type


# the parser generates ParserType, ParserFunctionHeader, ParserFunctionRef,
# ParserVariable. Those are later turned into Type, Function, Variable.

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class ParserType:
    location: Location
    name: str


# The "header" of the function is the "funcname(Blah b) -> Blah" part.

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class ParserFunctionHeaderArg:
    location: Location
    type: ParserType
    name: str


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class ParserFunctionHeader:
    name: str
    args: typing.List[ParserFunctionHeaderArg]
    returntype: typing.Optional[ParserType]     # None for ->void


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class ParserFunctionRef:
    name: str


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class ParserVariable:
    name: str


# ------------
# Now all parser garbage is done, and the actual ast creation begins
# ------------


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Statement:
    location: Location


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Expression(Statement):
    # this is optional because everything parses without types. Then types are
    # added in later.
    type: typing.Optional[Type]


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class StrConstant(Expression):
    python_string: str


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class StrJoin(Expression):
    parts: typing.List[Expression]


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class IntConstant(Expression):
    python_int: int


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class GetVar(Expression):
    var: typing.Optional[Variable]          # added in asdac.typer
    parser_var: ParserVariable


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class SetVar(Statement):
    var: typing.Optional[Variable]          # added in asdac.typer
    parser_var: ParserVariable


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Let(Statement):
    var: typing.Optional[Variable]          # added in asdac.typer
    parser_var: ParserVariable
    initial_value: Expression


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class FuncDefinition(Statement):
    parser_header: ParserFunctionHeader
    function: typing.Optional[Function]     # added in asdac.typer
    body: typing.List[Statement]


# Note that even void-function calls are valid expressions, although they
# create an error when the AST is type checked.
@attr.s(auto_attribs=True, cmp=False)
class CallFunction(Expression, Statement):
    parser_ref: ParserFunctionRef
    function: typing.Optional[Function]     # added in asdac.typer
    args: typing.List[Expression]


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Return(Statement):
    value: typing.Optional[Expression]


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class IfStatement(Statement):
    cond: Expression
    if_body: typing.List[Statement]
    else_body: typing.List[Statement]


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class IfExpression(Expression):
    cond: Expression
    true_expr: Expression
    false_expr: Expression


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Loop(Statement):
    pre_cond: Expression
    post_cond: Expression
    incr: typing.List[Statement]
    body: typing.List[Statement]
