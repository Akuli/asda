import collections
import functools

from . import objects


CREATE_FUNCTION = b'f'
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'     # only used in bytecode files
INT_CONSTANT = b'1'     # only used in bytecode files
TRUE_CONSTANT = b'T'    # only used in bytecode files
FALSE_CONSTANT = b'F'   # only used in bytecode files
CONSTANT = b'C'         # not used at all in bytecode files
LOOKUP_METHOD = b'm'
CALL_VOID_FUNCTION = b'('
CALL_RETURNING_FUNCTION = b')'
POP_ONE = b'P'
VOID_RETURN = b'r'
VALUE_RETURN = b'R'
DIDNT_RETURN_ERROR = b'd'
YIELD = b'Y'
NEGATION = b'!'
JUMP_IF = b'J'
END_OF_BODY = b'E'      # only used in bytecode files

TYPE_BUILTIN = b'b'
TYPE_GENERATOR = b'G'  # not to be confused with generator functions
TYPE_VOID = b'v'

Code = collections.namedtuple('Code', ['how_many_local_vars', 'opcodes'])


class _BytecodeReader:

    def __init__(self, read_callback):
        self._callback = read_callback    # no error on eof, returns b''
        self._push_buffer = bytearray()

    # errors on unexpected eof
    def _read(self, size):
        part1 = bytearray()
        while size > 0 and self._push_buffer:
            part1.append(self._push_buffer.pop())
            size -= 1

        part2 = self._callback(size)
        assert len(part2) == size
        return bytes(part1) + part2

    def _unread(self, byte):
        self._push_buffer.append(byte)

    def _read_uint(self, size):
        assert size % 8 == 0 and 0 < size <= 64, size
        result = 0
        for offset in range(0, size, 8):
            result |= self._read(1)[0] << offset
        return result

    read_uint8 = functools.partialmethod(_read_uint, 8)
    read_uint16 = functools.partialmethod(_read_uint, 16)
    read_uint32 = functools.partialmethod(_read_uint, 32)
    read_uint64 = functools.partialmethod(_read_uint, 64)

    def read_string(self):
        length = self.read_uint32()
        utf8 = self._read(length)
        return utf8.decode('utf-8')

    def read_type(self):
        magic = self._read(1)

        if magic == TYPE_BUILTIN:
            index = self.read_uint8()
            return list(objects.types.values())[index]

        elif magic == CREATE_FUNCTION:
            returntype = self.read_type()
            nargs = self.read_uint8()
            argtypes = [self.read_type() for junk in range(nargs)]
            return objects.FunctionType(argtypes, returntype)

        elif magic == TYPE_VOID:
            return None

        elif magic == TYPE_GENERATOR:
            return objects.GeneratorType(self.read_type())

        else:
            assert False

    def read_body(self):
        how_many_local_vars = self.read_uint16()
        opcode = []

        while True:
            magic = self._read(1)
            if magic == END_OF_BODY:
                break

            if magic == STR_CONSTANT:
                string_object = objects.String(self.read_string())
                opcode.append((CONSTANT, string_object))
            elif magic == TRUE_CONSTANT:
                opcode.append((CONSTANT, objects.TRUE))
            elif magic == FALSE_CONSTANT:
                opcode.append((CONSTANT, objects.FALSE))
            elif magic in {CALL_VOID_FUNCTION, CALL_RETURNING_FUNCTION}:
                opcode.append((magic, self.read_uint8()))
            elif magic in {LOOKUP_VAR, SET_VAR}:
                level = self.read_uint8()
                index = self.read_uint16()
                opcode.append((magic, level, index))
            elif magic in {POP_ONE, DIDNT_RETURN_ERROR, NEGATION, YIELD,
                           VOID_RETURN, VALUE_RETURN}:
                opcode.append((magic,))
            elif magic == CREATE_FUNCTION:
                self._unread(magic[0])
                tybe = self.read_type()
                yields = bool(self._read(1)[0])
                name = self.read_string()
                body = self.read_body()
                opcode.append((CREATE_FUNCTION, tybe, name, body, yields))
            elif magic == JUMP_IF:
                where2jump = self.read_uint16()
                opcode.append((JUMP_IF, where2jump))
            elif magic == LOOKUP_METHOD:
                tybe = self.read_type()
                index = self.read_uint16()
                opcode.append((LOOKUP_METHOD, tybe, index))
            else:
                assert False, magic

        return Code(how_many_local_vars, opcode)


def read_bytecode(read_callback):
    result = _BytecodeReader(read_callback).read_body()
    if read_callback(1) != b'':
        raise ValueError("junk at the end of the compiled file")
    return result
