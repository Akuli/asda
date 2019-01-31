import collections
import functools

from . import objects


SET_LINENO = b'L'

CREATE_FUNCTION = b'f'  # also used in types
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
STR_JOIN = b'j'
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

# args is a tuple whose elements depend on the kind
Op = collections.namedtuple('Op', ['lineno', 'kind', 'args'])


class _BytecodeReader:

    def __init__(self, read_callback):
        self._callback = read_callback    # no error on eof, returns b''
        self._push_buffer = bytearray()
        self._lineno = 1

    # errors on unexpected eof
    def _read(self, size):
        part1 = bytearray()
        while size > 0 and self._push_buffer:
            part1.append(self._push_buffer.pop())
            size -= 1

        part2 = self._callback(size)
        if len(part2) != size:
            raise RuntimeError("the bytecode file seems to be truncated")
        return bytes(part1) + part2

    def _unread(self, byte):
        self._push_buffer.append(byte)

    def _read_uint(self, size):
        assert size % 8 == 0 and 0 < size <= 64, size
        result = 0
        for offset in range(0, size, 8):
            result |= self._read(1)[0] << offset
        return result

    def _read_int(self, size):
        uint = self._read_uint(size)
        if uint >= 2**(size - 1):
            return uint - 2**size
        return uint

    read_uint8 = functools.partialmethod(_read_uint, 8)
    read_uint16 = functools.partialmethod(_read_uint, 16)
    read_uint32 = functools.partialmethod(_read_uint, 32)

    read_int64 = functools.partialmethod(_read_int, 64)

    def read_magic(self):
        magic = self._read(1)
        if magic == SET_LINENO:
            self._lineno = self.read_uint32()
            magic = self._read(1)
            assert magic != SET_LINENO
        return magic

    def read_string(self):
        length = self.read_uint32()
        utf8 = self._read(length)
        return utf8.decode('utf-8')

    def read_type(self):
        magic = self.read_magic()

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
            magic = self.read_magic()
            kind = magic

            if magic == END_OF_BODY:
                break
            elif magic == STR_CONSTANT:
                kind = CONSTANT
                args = (objects.String(self.read_string()),)
            elif magic == INT_CONSTANT:
                kind = CONSTANT
                args = (objects.Integer(self.read_int64()),)
            elif magic == TRUE_CONSTANT:
                kind = CONSTANT
                args = (objects.TRUE,)
            elif magic == FALSE_CONSTANT:
                kind = CONSTANT
                args = (objects.FALSE,)
            elif magic in {POP_ONE, DIDNT_RETURN_ERROR, NEGATION, YIELD,
                           VOID_RETURN, VALUE_RETURN}:
                args = ()
            elif magic in {CALL_VOID_FUNCTION, CALL_RETURNING_FUNCTION}:
                args = (self.read_uint8(),)
            elif magic in {JUMP_IF, STR_JOIN}:
                args = (self.read_uint16(),)
            elif magic in {LOOKUP_VAR, SET_VAR}:
                args = (self.read_uint8(), self.read_uint16())
            elif magic == LOOKUP_METHOD:
                args = (self.read_type(), self.read_uint16())
            elif magic == CREATE_FUNCTION:
                self._unread(magic[0])
                tybe = self.read_type()
                yields = bool(self._read(1)[0])
                name = self.read_string()
                body = self.read_body()
                args = (tybe, name, body, yields)
            else:
                assert False, magic

            opcode.append(Op(self._lineno, kind, args))

        return Code(how_many_local_vars, opcode)


def read_bytecode(read_callback):
    result = _BytecodeReader(read_callback).read_body()
    if read_callback(1) != b'':
        raise ValueError("junk at the end of the compiled file")
    return result
