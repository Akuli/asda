# converts decision tree to bytes that can be written to file

import bisect
import collections
import functools
import io
import os
import pathlib
import typing

from asdac import common, objects
from asdac import decision_tree as dtree
from asdac.common import Compilation, CompileError, Location


SET_LINENO = b'L'

GET_BUILTIN_VAR = b'U'
SET_ATTR = b':'
GET_ATTR = b'.'
GET_FROM_MODULE = b'm'
STR_CONSTANT = b'"'
NON_NEGATIVE_INT_CONSTANT = b'1'
NEGATIVE_INT_CONSTANT = b'2'
CALL_BUILTIN_FUNCTION = b'b'
CALL_THIS_FILE_FUNCTION = b'('
STR_JOIN = b'j'
RETURN = b'r'

DUP = b'D'
SWAP = b'S'
POP = b'P'

JUMP = b'K'
JUMP_IF = b'J'
JUMP_IF_INT_EQUAL = b'='
JUMP_IF_STR_EQUAL = b'q'

PLUS = b'+'
MINUS = b'-'
PREFIX_MINUS = b'_'
TIMES = b'*'
# DIVIDE = b'/'

EXPORT_OBJECT = b'x'

# these are used when bytecoding a type
TYPE_ASDA_CLASS = b'a'
TYPE_BUILTIN = b'b'
TYPE_FUNCTION = b'f'
TYPE_VOID = b'v'

IMPORT_SECTION = b'i'
EXPORT_SECTION = b'e'
TYPE_LIST_SECTION = b'y'


def _bit_storing_size(n: int) -> int:
    """Returns the number of bytes needed for storing n bits.

    >>> _bit_storing_size(16)
    2
    >>> _bit_storing_size(17)
    3
    """
    return -((-n) // 8)


# sometimes it's necessary to change an uint after adding it to bytecode
class _UintInByteCode:

    def __init__(self, byte_array: bytearray, offset: int, size: int):
        self._byte_array = byte_array
        self._offset = offset
        self._size = size

    def set(self, number: int) -> None:
        try:
            bytez = number.to_bytes(self._size, 'little')
        except OverflowError:
            raise CompileError(
                "this number does not fit in an unsigned %d-bit integer: %d"
                % (self._size * 8, number))

        self._byte_array[self._offset:self._offset+self._size] = bytez


class _Writer:

    def __init__(self, compilation: Compilation,
                 line_start_offsets: typing.List[int]):
        self.byte_array = bytearray()
        self.compilation = compilation
        self.line_start_offsets = line_start_offsets
        self.current_lineno = 1
        self.ops_written = 0

        # because functions may need to be referred to before they are written
        self.function_references: typing.Dict[
            objects.Function,
            typing.List[_UintInByteCode],   # uint16 referring to the function
        ] = {}
        self.function_definitions: typing.Dict[
            objects.Function,
            int,    # value to set to uint16
        ] = {}

    def _write_uint(self, bits: int, number: int) -> _UintInByteCode:
        r"""
        >>> bc = _ByteCode()
        >>> bc.write_uint16(1)
        >>> bc.get_bytes()
        b'\x01\x00'
        """
        assert bits % 8 == 0 and 0 < bits <= 64, bits

        result = _UintInByteCode(
            self.byte_array, len(self.byte_array), bits // 8)
        result.set(number)   # this makes self.byte_array longer
        return result

    write_uint8 = functools.partialmethod(_write_uint, 8)
    write_uint16 = functools.partialmethod(_write_uint, 16)
    write_uint32 = functools.partialmethod(_write_uint, 32)

    def write_big_uint(self, abs_value: int) -> None:
        assert abs_value >= 0
        size = _bit_storing_size(abs_value.bit_length())
        self.write_uint32(size)
        self.byte_array.extend(abs_value.to_bytes(size, 'little'))

    def write_string(self, string: str) -> None:
        utf8 = string.encode('utf-8')
        self.write_uint32(len(utf8))
        self.byte_array.extend(utf8)

    def write_path(self, path: pathlib.Path) -> None:
        relative2 = self.compilation.compiled_path.parent
        relative_path = common.relpath(path, relative2)

        # asda-compiled/whatever.asdac should always be in lowercase, and other
        # code should ensure that
        assert str(relative_path).islower()

        # forward slash to make the compiled bytecodes cross-platform
        self.write_string(str(relative_path).replace(os.sep, '/'))

    def write_opbyte(self, byte: bytes) -> None:
        assert len(byte) == 1
        self.byte_array.extend(byte)
        self.ops_written += 1

    def set_lineno(self, location: Location) -> None:
        #    >>> offsets = [0, 4, 10]
        #    >>> bisect.bisect(offsets, 0)
        #    1
        #    >>> bisect.bisect(offsets, 3)
        #    1
        #    >>> bisect.bisect(offsets, 4)
        #    2
        #    >>> bisect.bisect(offsets, 8)
        #    2
        #    >>> bisect.bisect(offsets, 9)
        #    2
        #    >>> bisect.bisect(offsets, 10)
        #    3
        assert location.compilation is self.compilation
        lineno = bisect.bisect(self.line_start_offsets, location.offset)
        if lineno != self.current_lineno:
            self.byte_array.extend(SET_LINENO)
            self.write_uint32(lineno)
            self.current_lineno = lineno

    def fix_function_references(self) -> None:
        for func, refs in self.function_references.items():
            for ref in refs:
                ref.set(self.function_definitions[func])


class _ByteCodeGen:

    def __init__(self, writer: _Writer, arg_ids: typing.List[dtree.ObjectId]):
        self.writer = writer
        self.stack = list(arg_ids)
        self.jump_cache: typing.Dict[dtree.Node, int] = {}

    def _write_dup(self, id: dtree.ObjectId) -> None:
        assert id in self.stack     # might be in it more than once
        last_index_from_end = self.stack[::-1].index(id)
        self.writer.write_opbyte(DUP)
        self.writer.write_uint16(last_index_from_end)
        self.stack.append(id)

    def _write_swap(self, index1: int, index2: int) -> None:
        if index1 == index2:
            return

        self.writer.write_opbyte(SWAP)
        self.writer.write_uint16(index1)
        self.writer.write_uint16(index2)

        # assigning to self.stack[::-1][index1] doesn't work :(
        i1 = len(self.stack) - index1 - 1
        i2 = len(self.stack) - index2 - 1
        self.stack[i1], self.stack[i2] = self.stack[i2], self.stack[i1]

    def _get_objects_to_top_of_stack(
        self,
        current_node: dtree.Node,
        want2top: typing.List[dtree.ObjectId],
    ) -> None:
        # sanity checks
        for id in want2top:
            assert id in self.stack
        for id in self.stack:
            assert self.stack.count(id) == 1

        # which id's are used after running current_node?
        needed_later = set()
        for node in dtree.get_all_nodes(current_node, include_root=False):
            needed_later.update(node.ids_read())

        # put more of the same object on the stack as needed
        for id in set(want2top):
            if id in needed_later:
                how_many_available = 0
            else:
                how_many_available = 1

            while how_many_available < want2top.count(id):
                self._write_dup(id)
                how_many_available += 1
            assert how_many_available == want2top.count(id)

        # rearrange objects on stack
        for new_index, id in enumerate(reversed(want2top)):
            current_index = self.stack[::-1].index(id, new_index)
            if new_index != current_index:
                self._write_swap(current_index, new_index)

    def _delete_n_topmost_from_stack(self, n: int) -> None:
        # python slicing is fun: 'del self.stack[-0:]' deletes everything
        if n > 0:
            del self.stack[-n:]

    def write_pass_through_node(
            self, node: dtree.PassThroughNode) -> None:
        if isinstance(node, dtree.StrConstant):
            self.writer.write_opbyte(STR_CONSTANT)
            self.writer.write_string(node.python_string)
            self.stack.append(node.result_id)
            return

        if isinstance(node, dtree.IntConstant):
            if node.python_int >= 0:
                self.writer.write_opbyte(NON_NEGATIVE_INT_CONSTANT)
                self.writer.write_big_uint(node.python_int)
            else:
                # currently this code never runs because -2 is parsed as the
                # prefix minus operator applied to the non-negative integer
                # constant 2, but i'm planning on adding an optimizer that
                # would output it as a thing that needs this code
                self.writer.write_opbyte(NEGATIVE_INT_CONSTANT)
                self.writer.write_big_uint(abs(node.python_int))

            self.stack.append(node.result_id)
            return

        if isinstance(node, dtree.GetBuiltinVar):
            self.writer.write_opbyte(GET_BUILTIN_VAR)
            self.writer.write_uint8(
                list(objects.BUILTIN_VARS.values()).index(node.var))
            self.stack.append(node.result_id)
            return

        if isinstance(node, dtree.CallFunction):
            self._get_objects_to_top_of_stack(node, node.arg_ids)

            if node.function.kind == objects.FunctionKind.BUILTIN:
                self.writer.write_opbyte(CALL_BUILTIN_FUNCTION)
                # TODO: identify the function somehow instead of assuming that
                #       it's print
            elif node.function.kind == objects.FunctionKind.FILE:
                self.writer.write_opbyte(CALL_THIS_FILE_FUNCTION)
                self.writer.function_references.setdefault(
                    node.function, []).append(self.writer.write_uint16(0))
            else:
                raise NotImplementedError

            self.writer.write_uint16(len(node.arg_ids))
            self._delete_n_topmost_from_stack(len(node.arg_ids))

            if node.result_id is not None:
                self.stack.append(node.result_id)
            return

        if isinstance(node, dtree.StrJoin):
            self._get_objects_to_top_of_stack(node, node.string_ids)
            self.writer.write_opbyte(STR_JOIN)
            self.writer.write_uint16(len(node.string_ids))
            self._delete_n_topmost_from_stack(len(node.string_ids))
            self.stack.append(node.result_id)
            return

        assert False, node        # pragma: no cover

    def write_2_way_decision(self, node: dtree.TwoWayDecision) -> None:
        # this does not output the same bytecode twice
        # for example, consider this code
        #
        #    a
        #    if b:
        #        c
        #    else:
        #        d
        #    e
        #
        # it creates a tree like this
        #
        #     a
        #     |
        #     b
        #    / \
        #   c   d
        #    \ /
        #     e
        #
        # and opcode like this
        #
        #    a
        #    b
        #    if b is true, jump to then_marker
        #    d
        #    e
        #    jump to done_marker
        #    then_marker
        #    c
        #    jump to e
        #    done_marker
        #
        # the 'jump to e' part gets added by jump_cache stuff, because e has
        # already gotten opcoded once and can be reused
        #
        # this is not ideal, could be pseudo-optimized to do less jumps, but
        # that's likely not a bottleneck so why bother

        if isinstance(node, dtree.BoolDecision):
            self.writer.write_opbyte(JUMP_IF)
        elif isinstance(node, dtree.IntEqualDecision):
            self.writer.write_opbyte(JUMP_IF_INT_EQUAL)
        elif isinstance(node, dtree.StrEqualDecision):
            self.writer.write_opbyte(JUMP_IF_STR_EQUAL)
        else:  # pragma: no cover
            raise RuntimeError
        then_jump = self.writer.write_uint16(0)

        self.write_tree(node.otherwise)

        self.writer.write_opbyte(JUMP)
        done_jump = self.writer.write_uint16(0)

        then_jump.set(self.writer.ops_written)
        self.write_tree(node.then)
        done_jump.set(self.writer.ops_written)

    def write_tree(self, node: typing.Optional[dtree.Node]) -> None:
        while node is not None:
            if node in self.jump_cache:
                self.writer.write_opbyte(JUMP)
                self.writer.write_uint16(self.jump_cache[node])
                return

            if len(node.jumped_from) > 1:
                self.jump_cache[node] = self.writer.ops_written

            self.writer.set_lineno(node.location)
            if isinstance(node, dtree.PassThroughNode):
                self.write_pass_through_node(node)
                node = node.next_node
            elif isinstance(node, dtree.TwoWayDecision):
                self.write_2_way_decision(node)
                return
            else:
                raise NotImplementedError("omg " + repr(node))

        self.writer.write_opbyte(RETURN)

    def write_function_opcode(
            self,
            function: objects.Function,
            start_node: dtree.Start) -> None:
        assert function.kind == objects.FunctionKind.FILE
        self.writer.function_definitions[function] = self.writer.ops_written

        op_count = self.writer.write_uint16(0)
        old_op_index = self.writer.ops_written
        self.stack.extend(start_node.arg_ids)
        self.write_tree(start_node.next_node)
        op_count.set(self.writer.ops_written - old_op_index)


# structure of a bytecode file:
#   1.  the bytes b'asda\xA5\xDA'  (note how 5 looks like S, lol)
#   2.  source path string, relative to the dirname of the compiled path
#   3.  opcode of each function
#
# all paths are relative to the bytecode file's directory and have '/' as
# the separator
def create_bytecode(
        compilation: Compilation,
        function_trees: typing.Dict[objects.Function, dtree.Start],
        source_code: str) -> bytearray:
    # TODO: are these counted in bytes or unicode characters?
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    # make sure that main is first
    funclist = sorted(function_trees.keys(),
                      key=(lambda f: 1 if f.is_main else 2))
    assert funclist[0].is_main
    if len(funclist) >= 2:
        assert not funclist[1].is_main

    writer = _Writer(compilation, line_start_offsets)
    writer.byte_array.extend(b'asda\xA5\xDA')
    writer.write_path(compilation.source_path)
    writer.write_uint16(len(function_trees))

    for func in funclist:
        gen = _ByteCodeGen(writer, [])
        gen.write_function_opcode(func, function_trees[func])

    writer.fix_function_references()
    return writer.byte_array
