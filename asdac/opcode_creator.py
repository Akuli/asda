import collections
import typing

import attr

from asdac import opcode
from asdac import decision_tree as dtree
from asdac.common import Location
from asdac.objects import Function


T = typing.TypeVar('T')


# lizt[-n:] doesn't do the right thing when n=0
def _delete_top(lizt: typing.List[T], top: typing.List[T]) -> None:
    if top:
        assert lizt[-len(top):] == top
        del lizt[-len(top):]


def _object_needed_recurser(
    *,
    node: dtree.Node,
    id: dtree.ObjectId,
    first_time_ignoring: bool,
    visited: typing.Set[dtree.Node],
) -> bool:

    # i spent quite a while thinking through this logic carefully...

    if id in node.ids_read() and not first_time_ignoring:
        # node may be the first node in our recursion even if this isn't the
        # first time the recurser is called. Then we have a loop that goes back
        # to the same node.
        return True

    if id in node.ids_written():
        return False

    if node in visited:
        return False

    return any(
        _object_needed_recurser(
            node=other_node,
            id=id,
            first_time_ignoring=False,
            visited=(visited | {node})
        )
        for other_node in node.get_jumps_to()
    )


def _object_needed(node: dtree.Node, id: dtree.ObjectId, *,
                   may_need_now: bool) -> bool:
    return _object_needed_recurser(
        node=node,
        id=id,
        first_time_ignoring=(not may_need_now),
        visited=set(),
    )


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True)
class JumpInfo:
    marker: opcode.JumpMarker
    stack: typing.List[dtree.ObjectId]


class _OpCodeCreator:

    def __init__(self) -> None:
        self.opcode: opcode.OpCode = []
        self.stack: typing.List[dtree.ObjectId] = []
        self.jump_cache: typing.Dict[dtree.Node, JumpInfo] = {}

    def _convert_index(self, index: int) -> int:
        """
        There are two kinds of indexes:
        - start-relative: 0 --> self.stack[0], 1 --> self.stack[1], ...
        - end-relative: 0 --> self.stack[-1], 1 --> self.stack[-2], ...

        This converts from start-relative to end-relative OR from end-relative
        to start-relative. Have fun figuring out why the same code handles both
        without a parameter telling it which kind of conversion it should do.
        """
        return len(self.stack) - index - 1

    # consider using this instead of self.stack.append(id) to avoid duplicates
    def _put_id_to_stack(
            self, loc: typing.Optional[Location], id: dtree.ObjectId) -> None:

        if id in self.stack:
            assert self.stack.count(id) == 1

            # TODO: is this a runtime perf bottleneck?
            self.opcode.append(opcode.Swap(loc, 0, self.stack[::-1].index(id)))
            self.opcode.append(opcode.Pop(loc))

        else:
            self.stack.append(id)

        assert self.stack.count(id) == 1

    def _dup(self, loc: typing.Optional[Location], id: dtree.ObjectId) -> None:
        self.opcode.append(opcode.Dup(loc, self.stack[::-1].index(id)))
        self.stack.append(id)

    def _pop(self, loc: typing.Optional[Location]) -> None:
        self.opcode.append(opcode.Pop(loc))
        del self.stack[-1]

    def _dup_to_count(
            self, node: dtree.Node, id: dtree.ObjectId, need: int) -> None:

        have = 0 if _object_needed(node, id, may_need_now=False) else 1
        assert need >= 0
        while have < need:
            self._dup(node.location, id)
            have += 1

    def _swap(
            self, loc: typing.Optional[Location],
            index1: int, index2: int) -> None:

        assert index1 >= 0
        assert index2 >= 0
        if index1 == index2:
            return

        self.opcode.append(opcode.Swap(loc, index1, index2))

        # assigning to self.stack[::-1][index1] doesn't work in python :(
        i1 = self._convert_index(index1)
        i2 = self._convert_index(index2)
        self.stack[i1], self.stack[i2] = self.stack[i2], self.stack[i1]

    def _rearrange_stack_top_or_bottom(
            self, loc: typing.Optional[Location],
            id_list: typing.List[dtree.ObjectId], *, top: bool) -> None:

        if top:
            for index, id in enumerate(id_list[::-1]):
                # Passing the index variable as second arg to .index() method
                # prevents this from screwing up the work done on earlier
                # iterations.
                where_is_it = self.stack[::-1].index(id, index)
                self._swap(loc, where_is_it, index)
        else:
            for index, id in enumerate(id_list):
                where_is_it = self.stack.index(id, index)
                self._swap(loc, self._convert_index(where_is_it),
                           self._convert_index(index))

    def get_ids_to_top_or_bottom_of_stack(
            self, node: dtree.Node,
            id_list: typing.List[dtree.ObjectId], *, top: bool) -> None:

        for id in id_list:
            assert id in self.stack
            assert self.stack.count(id) == 1

        for id, need in dict(collections.Counter(id_list)).items():
            self._dup_to_count(node, id, need)

        self._rearrange_stack_top_or_bottom(node.location, id_list, top=top)

    def make_stack_to_be(
            self, loc: typing.Optional[Location],
            new_stack: typing.List[dtree.ObjectId]) -> None:

        self._rearrange_stack_top_or_bottom(loc, new_stack, top=False)
        while self.stack != new_stack:
            self._pop(loc)

    def node2opcode(self, node: typing.Optional[dtree.Node]) -> None:
        if node is None:
            return

        # must be no duplicates
        assert len(self.stack) == len(set(self.stack))      # no duplicates

        # clean up unnecessary ids from stack (necessary for jump caching)
        self.make_stack_to_be(node.location, [
            id for id in self.stack
            if _object_needed(node, id, may_need_now=True)
        ])

        # avoid repeating same opcode more than once
        if node in self.jump_cache:
            # If this fails, then stacks cleanup above is not cleaning up all
            # the junk, or some object ids are missing from a stack when they
            # shouldn't be.
            assert set(self.stack) == set(self.jump_cache[node].stack)

            self.make_stack_to_be(node.location, self.jump_cache[node].stack)
            self.opcode.append(opcode.Jump(
                node.location, self.jump_cache[node].marker))
            return

        marker = opcode.JumpMarker()
        self.jump_cache[node] = JumpInfo(marker, self.stack.copy())
        self.opcode.append(marker)

        if isinstance(node, dtree.Start):
            self.stack.extend(node.arg_ids)
            self.node2opcode(node.next_node)

        elif isinstance(node, dtree.IntConstant):
            self.opcode.append(opcode.IntConstant(
                node.location, node.python_int))
            self._put_id_to_stack(node.location, node.result_id)
            self.node2opcode(node.next_node)

        elif isinstance(node, dtree.StrConstant):
            self.opcode.append(opcode.StrConstant(
                node.location, node.python_string))
            self._put_id_to_stack(node.location, node.result_id)
            self.node2opcode(node.next_node)

        elif isinstance(node, dtree.GetBuiltinVar):
            self.opcode.append(opcode.GetBuiltinVar(node.location, node.var))
            self._put_id_to_stack(node.location, node.result_id)
            self.node2opcode(node.next_node)

        elif isinstance(node, dtree.CallFunction):
            self.get_ids_to_top_or_bottom_of_stack(
                node, node.arg_ids, top=True)
            self.opcode.append(opcode.CallFunction(
                node.location, node.function))
            _delete_top(self.stack, node.arg_ids)

            if node.result_id is not None:
                self._put_id_to_stack(node.location, node.result_id)
            self.node2opcode(node.next_node)

        elif isinstance(node, dtree.StrJoin):
            self.get_ids_to_top_or_bottom_of_stack(
                node, node.string_ids, top=True)
            self.opcode.append(opcode.StrJoin(
                node.location, len(node.string_ids)))
            _delete_top(self.stack, node.string_ids)
            self._put_id_to_stack(node.location, node.result_id)
            self.node2opcode(node.next_node)

        elif isinstance(node, dtree.Return):
            if node.value_id is None:
                self.make_stack_to_be(node.location, [])
            else:
                self.make_stack_to_be(node.location, [node.value_id])
            self.opcode.append(opcode.Return(node.location))

        elif isinstance(node, dtree.Assign):
            popped = self.stack.pop()
            assert popped is node.input_id
            self._put_id_to_stack(node.location, node.result_id)
            self.node2opcode(node.next_node)

        elif isinstance(node, dtree.BoolDecision):
            then_marker = opcode.JumpMarker()

            self.get_ids_to_top_or_bottom_of_stack(
                node, [node.input_id], top=True)
            self.opcode.append(opcode.JumpIf(node.location, then_marker))
            condition = self.stack.pop()
            assert condition is node.input_id

            original_stack = self.stack.copy()
            self.node2opcode(node.otherwise)

            self.stack = original_stack
            self.opcode.append(then_marker)
            self.node2opcode(node.then)

        else:
            raise NotImplementedError(node)


def _clean_unnecessary_jump_markers(ops: opcode.OpCode) -> opcode.OpCode:
    needed_markers = {
        op.where2jump for op in ops
        if isinstance(op, (opcode.Jump, opcode.JumpIf))
    }
    return [
        op for op in ops
        if op in needed_markers or not isinstance(op, opcode.JumpMarker)
    ]


def _create_function_opcode(start: dtree.Start) -> opcode.OpCode:
    creator = _OpCodeCreator()
    creator.node2opcode(start)
    return _clean_unnecessary_jump_markers(creator.opcode)


def create_opcode(
    function_trees: typing.Dict[Function, dtree.Start],
) -> typing.Dict[Function, opcode.OpCode]:
    return {func: _create_function_opcode(start)
            for func, start in function_trees.items()}
