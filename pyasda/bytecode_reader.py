import collections
import functools
import os
import pathlib

from . import objects


SET_LINENO = b'L'   # only used in bytecode files

CREATE_FUNCTION = b'f'  # also used in types
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'             # only used in bytecode files
NON_NEGATIVE_INT_CONSTANT = b'1'    # only used in bytecode files
NEGATIVE_INT_CONSTANT = b'2'    # only used in bytecode files
TRUE_CONSTANT = b'T'            # only used in bytecode files
FALSE_CONSTANT = b'F'           # only used in bytecode files
CONSTANT = b'C'                 # not used at all in bytecode files
LOOKUP_ATTRIBUTE = b'.'
IMPORT_MODULE = b'M'    # also used in types
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
IMPORT_SECTION = b'i'   # only used in bytecode files

PLUS = b'+'
MINUS = b'-'
PREFIX_MINUS = b'_'
TIMES = b'*'
# DIVIDE = b'/'
EQUAL = b'='

# these are only used in bytecode files
TYPE_BUILTIN = b'b'
TYPE_GENERATOR = b'G'  # not to be confused with generator functions
TYPE_VOID = b'v'

Code = collections.namedtuple('Code', ['how_many_local_vars', 'opcodes'])

# args is a tuple whose elements depend on the kind
Op = collections.namedtuple('Op', ['lineno', 'kind', 'args'])


class _BytecodeReader:

    def __init__(self, compiled_path, file, module_getter):
        self.compiled_path = compiled_path
        self.file = file
        self._push_buffer = bytearray()
        self._lineno = 1
        self.get_module = module_getter

    # errors on unexpected eof
    def _read(self, size):
        part1 = bytearray()
        while size > 0 and self._push_buffer:
            part1.append(self._push_buffer.pop())
            size -= 1

        part2 = self.file.read(size)
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

    read_uint8 = functools.partialmethod(_read_uint, 8)
    read_uint16 = functools.partialmethod(_read_uint, 16)
    read_uint32 = functools.partialmethod(_read_uint, 32)

    def read_big_uint(self):
        # c rewrite notes: use mpz_init2, mpz_mul_2exp, mpz_ior
        byte_count = self.read_uint32()
        result = 0
        for index, byte in enumerate(self._read(byte_count)):
            result <<= 8
            result |= byte
        return result

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

        if magic == CREATE_FUNCTION:
            returntype = self.read_type()
            nargs = self.read_uint8()
            argtypes = [self.read_type() for junk in range(nargs)]
            return objects.FunctionType(argtypes, returntype)

        if magic == TYPE_VOID:
            return None

        if magic == TYPE_GENERATOR:
            return objects.GeneratorType(self.read_type())

        if magic == IMPORT_MODULE:
            return self.get_module(self.read_path()).type

        assert False, magic

    def read_path(self):
        relative_path = pathlib.Path(*self.read_string().split('/'))
        result = self.compiled_path.parent / relative_path

        # os.path.abspath deletes '..' parts from paths
        return pathlib.Path(os.path.abspath(str(result)))

    def read_imports(self):
        if self.read_magic() != IMPORT_SECTION:
            raise RuntimeError("oh no!")

        how_many = self.read_uint32()
        result = []
        for lel in range(how_many):
            result.append(self.read_path())

        return result

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
            elif magic in {NON_NEGATIVE_INT_CONSTANT, NEGATIVE_INT_CONSTANT}:
                kind = CONSTANT
                value = self.read_big_uint()
                if magic == NEGATIVE_INT_CONSTANT:
                    value = -value
                args = (objects.Integer(value),)
            elif magic == TRUE_CONSTANT:
                kind = CONSTANT
                args = (objects.TRUE,)
            elif magic == FALSE_CONSTANT:
                kind = CONSTANT
                args = (objects.FALSE,)
            elif magic in {POP_ONE, DIDNT_RETURN_ERROR, NEGATION, YIELD,
                           VOID_RETURN, VALUE_RETURN, PLUS, MINUS,
                           PREFIX_MINUS, TIMES,  # DIVIDE,
                           EQUAL}:
                args = ()
            elif magic in {CALL_VOID_FUNCTION, CALL_RETURNING_FUNCTION}:
                args = (self.read_uint8(),)
            elif magic in {JUMP_IF, STR_JOIN}:
                args = (self.read_uint16(),)
            elif magic in {LOOKUP_VAR, SET_VAR}:
                args = (self.read_uint8(), self.read_uint16())
            elif magic == LOOKUP_ATTRIBUTE:
                args = (self.read_type(), self.read_uint16())
            elif magic == IMPORT_MODULE:
                args = (self.read_path(),)
            elif magic == CREATE_FUNCTION:
                self._unread(magic[0])
                tybe = self.read_type()
                yields = bool(self._read(1)[0])
                body = self.read_body()
                args = (tybe, body, yields)
            else:
                assert False, magic

            opcode.append(Op(self._lineno, kind, args))

        return Code(how_many_local_vars, opcode)


def read_bytecode(compiled_path, file, module_getter):
    if file.read(4) != b'asda':
        raise RuntimeError(
            "doesn't look like a compiled asda file: " + compiled_path)

    opcode = _BytecodeReader(compiled_path, file, module_getter).read_body()

    if file.read(1) != IMPORT_SECTION:
        raise ValueError("the bytecode file ends unexpectedly")
    return opcode
