# converts decision tree to bytes that can be written to file

import bisect
import contextlib
import functools
import io
import os
import pathlib
import typing

import attr

from asdac import common, objects, opcode
from asdac import decision_tree as dtree
from asdac.common import Compilation, CompileError, Location


SET_LINENO = b'L'

GET_BUILTIN_VAR = b'U'
STR_CONSTANT = b'"'
NON_NEGATIVE_INT_CONSTANT = b'1'
NEGATIVE_INT_CONSTANT = b'2'
CALL_BUILTIN_FUNCTION = b'b'
CALL_THIS_FILE_FUNCTION = b'('
STR_JOIN = b'j'
RETURN = b'r'
THROW = b't'
DUP = b'D'
SWAP = b'S'
POP = b'P'
JUMP = b'K'
JUMP_IF = b'J'


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
        bytez = number.to_bytes(self._size, 'little')
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

    def set_lineno(self, location: typing.Optional[Location]) -> None:
        if location is None:
            return

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

    def __init__(self, writer: _Writer):
        self.writer = writer

        self._marker2uintlist: typing.Dict[
            opcode.JumpMarker, typing.List[_UintInByteCode]
        ] = {}
        self._marker2index: typing.Dict[opcode.JumpMarker, int] = {}

    def write_op(self, op: typing.Union[opcode.Op, opcode.JumpMarker]):
        if isinstance(op, opcode.JumpMarker):
            self._marker2index[op] = self.writer.ops_written
            return

        self.writer.set_lineno(op.location)

        if isinstance(op, opcode.IntConstant):
            if op.python_int >= 0:
                self.writer.write_opbyte(NON_NEGATIVE_INT_CONSTANT)
                self.writer.write_big_uint(op.python_int)
            else:
                # currently this code never runs because -2 is parsed as the
                # prefix minus operator applied to the non-negative integer
                # constant 2, but i'm planning on adding an optimizer that
                # would output it as a thing that needs this code
                self.writer.write_opbyte(NEGATIVE_INT_CONSTANT)
                self.writer.write_big_uint(abs(op.python_int))

        elif isinstance(op, opcode.Dup):
            self.writer.write_opbyte(DUP)
            self.writer.write_uint16(op.index)

        elif isinstance(op, opcode.Swap):
            self.writer.write_opbyte(SWAP)
            self.writer.write_uint16(op.index1)
            self.writer.write_uint16(op.index2)

        elif isinstance(op, opcode.CallFunction):
            if op.func.kind == objects.FunctionKind.BUILTIN:
                self.writer.write_opbyte(CALL_BUILTIN_FUNCTION)
                self.writer.write_string(op.func.name)
            elif op.func.kind == objects.FunctionKind.FILE:
                self.writer.write_opbyte(CALL_THIS_FILE_FUNCTION)
                ref = self.writer.write_uint16(0)
                self.writer.function_references.setdefault(
                    op.func, []).append(ref)
                self.writer.write_uint16(len(op.func.argvars))
            else:
                raise NotImplementedError

        elif isinstance(op, opcode.Jump):
            self.writer.write_opbyte(JUMP)
            uint = self.writer.write_uint16(0)
            self._marker2uintlist.setdefault(op.where2jump, []).append(uint)

        elif isinstance(op, opcode.JumpIf):
            self.writer.write_opbyte(JUMP_IF)
            uint = self.writer.write_uint16(0)
            self._marker2uintlist.setdefault(op.where2jump, []).append(uint)

        elif isinstance(op, opcode.Pop):
            self.writer.write_opbyte(POP)

        elif isinstance(op, opcode.GetBuiltinVar):
            self.writer.write_opbyte(GET_BUILTIN_VAR)
            self.writer.write_uint8(
                list(objects.BUILTIN_VARS.values()).index(op.var))

        elif isinstance(op, opcode.StrConstant):
            self.writer.write_opbyte(STR_CONSTANT)
            self.writer.write_string(op.python_str)

        elif isinstance(op, opcode.Return):
            self.writer.write_opbyte(RETURN)

        else:
            raise NotImplementedError(op)

    def write_function_opcode(
            self,
            function: objects.Function,
            ops: opcode.OpCode) -> None:
        assert function.kind == objects.FunctionKind.FILE
        self.writer.function_definitions[function] = self.writer.ops_written

        op_count = self.writer.write_uint16(0)
        old_op_index = self.writer.ops_written
        for op in ops:
            self.write_op(op)
        op_count.set(self.writer.ops_written - old_op_index)

    def fix_jump_references(self):
        for marker, uints in self._marker2uintlist.items():
            for uint in uints:
                uint.set(self._marker2index[marker])


# structure of a bytecode file:
#   1.  the bytes b'asda\xA5\xDA'  (note how 5 looks like S, lol)
#   2.  source path string, relative to the dirname of the compiled path
#   3.  opcode of each function
#
# all paths are relative to the bytecode file's directory and have '/' as
# the separator
def create_bytecode(
        compilation: Compilation,
        function_opcodes: typing.Dict[objects.Function, opcode.OpCode],
        source_code: str) -> bytearray:
    # TODO: are these counted in bytes or unicode characters?
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    # make sure that main is first
    funclist = sorted(function_opcodes.keys(),
                      key=(lambda f: 1 if f.is_main else 2))
    assert funclist[0].is_main
    if len(funclist) >= 2:
        assert not funclist[1].is_main

    writer = _Writer(compilation, line_start_offsets)
    writer.byte_array.extend(b'asda\xA5\xDA')
    writer.write_path(compilation.source_path)
    writer.write_uint16(len(function_opcodes))

    for func in funclist:
        gen = _ByteCodeGen(writer)
        gen.write_function_opcode(func, function_opcodes[func])
        gen.fix_jump_references()

    writer.fix_function_references()
    return writer.byte_array
