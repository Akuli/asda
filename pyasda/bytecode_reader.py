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
CALL_VOID_FUNCTION = b'('
CALL_RETURNING_FUNCTION = b')'
POP_ONE = b'P'
VOID_RETURN = b'r'
VALUE_RETURN = b'R'
NEGATION = b'!'
JUMP_IF = b'J'
END_OF_BODY = b'E'      # only used in bytecode files

Code = collections.namedtuple('Code', ['how_many_local_vars', 'opcodes'])


class _BytecodeReader:

    def __init__(self, read_callback):
        self._maybe_read = read_callback    # no error on eof, returns b''

    # errors on unexpected eof
    def _read(self, size):
        result = self._maybe_read(size)
        assert len(result) == size
        return result

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

    def read_body(self):
        how_many_local_vars = self.read_uint16()
        opcode = []

        while True:
            magic = self._maybe_read(1)
            if magic == END_OF_BODY:
                break

            if magic == STR_CONSTANT:
                string_object = objects.AsdaString(self.read_string())
                opcode.append((CONSTANT, string_object))
            elif magic == TRUE_CONSTANT:
                opcode.append((CONSTANT, objects.TRUE))
            elif magic == FALSE_CONSTANT:
                opcode.append((CONSTANT, objects.FALSE))
            elif magic == CALL_VOID_FUNCTION:
                opcode.append((CALL_VOID_FUNCTION, self.read_uint8()))
            elif magic == CALL_RETURNING_FUNCTION:
                opcode.append((CALL_RETURNING_FUNCTION, self.read_uint8()))
            elif magic == LOOKUP_VAR:
                level = self.read_uint8()
                index = self.read_uint16()
                opcode.append((LOOKUP_VAR, level, index))
            elif magic == SET_VAR:
                level = self.read_uint8()
                index = self.read_uint16()
                opcode.append((SET_VAR, level, index))
            elif magic == POP_ONE:
                opcode.append((POP_ONE,))
            elif magic == CREATE_FUNCTION:
                name = self.read_string()
                body = self.read_body()
                opcode.append((CREATE_FUNCTION, name, body))
            elif magic == VOID_RETURN:
                opcode.append((VOID_RETURN,))
            elif magic == VALUE_RETURN:
                opcode.append((VALUE_RETURN,))
            elif magic == JUMP_IF:
                where2jump = self.read_uint16()
                opcode.append((JUMP_IF, where2jump))
            elif magic == NEGATION:
                opcode.append((NEGATION,))
            else:
                assert False, magic

        return Code(how_many_local_vars, opcode)


def read_bytecode(read_callback):
    asda = read_callback(4)
    if asda != b'asda':
        raise ValueError("doesn't look like a compiled asda file")

    reader = _BytecodeReader(read_callback)
    result = reader.read_body()

    if read_callback(1) != b'':
        raise ValueError("junk at the end of the compiled file")
    return result
