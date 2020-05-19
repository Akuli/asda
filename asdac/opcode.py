import typing

import attr

from asdac.common import Location
from asdac.objects import Function, Variable


_jumpmarker_debug_ids: typing.Dict['JumpMarker', int] = {}


class JumpMarker:

    def __repr__(self) -> str:
        if self not in _jumpmarker_debug_ids:
            _jumpmarker_debug_ids[self] = len(_jumpmarker_debug_ids)
        return f"<{__name__}.JumpMarker {_jumpmarker_debug_ids[self]}>"


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Op:
    location: typing.Optional[Location]


OpCode = typing.List[typing.Union[JumpMarker, Op]]


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class GetBuiltinVar(Op):
    var: Variable = attr.ib()


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class StrConstant(Op):
    python_str: str


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class IntConstant(Op):
    python_int: int


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class CallFunction(Op):
    func: Function


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class StrJoin(Op):
    how_many_strings: int


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Return(Op):
    pass


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Throw(Op):
    pass


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Dup(Op):
    # all indexes are so that 0 is the topmost item on stack
    index: int


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Swap(Op):
    index1: int
    index2: int


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Pop(Op):
    pass


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class Jump(Op):
    where2jump: JumpMarker


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class JumpIf(Op):
    where2jump: JumpMarker
