import collections
import functools
import io

from . import common, objects, opcoder


SET_LINENO = b'L'

CREATE_FUNCTION = b'f'     # also used when bytecoding a type
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'
NON_NEGATIVE_INT_CONSTANT = b'1'
NEGATIVE_INT_CONSTANT = b'2'
TRUE_CONSTANT = b'T'
FALSE_CONSTANT = b'F'
LOOKUP_METHOD = b'm'
CALL_VOID_FUNCTION = b'('
CALL_RETURNING_FUNCTION = b')'
STR_JOIN = b'j'
POP_ONE = b'P'
VOID_RETURN = b'r'
VALUE_RETURN = b'R'
DIDNT_RETURN_ERROR = b'd'
YIELD = b'Y'
BOOL_NEGATION = b'!'
JUMP_IF = b'J'
END_OF_BODY = b'E'
EXPORT_SECTION = b'e'

PLUS = b'+'
MINUS = b'-'
PREFIX_MINUS = b'_'
TIMES = b'*'
#DIVIDE = b'/'
EQUAL = b'='

# these are used when bytecoding a type
TYPE_BUILTIN = b'b'
TYPE_GENERATOR = b'G'  # not to be confused with generator functions
TYPE_VOID = b'v'


class _ByteCode:

    def __init__(self):
        self.byte_array = bytearray()
        self.current_lineno = 1

    # writes an unsigned little-endian integer
    def _add_uint(self, size, number):
        assert size % 8 == 0 and 0 < size <= 64, size
        assert number >= 0
        if number >= 2**size:
            raise common.CompileError(
                "this number does not fit in an unsigned %d-bit integer: %d"
                % (size, number))

        self.byte_array.extend((number >> offset) & 0xff
                               for offset in range(0, size, 8))

    add_uint8 = functools.partialmethod(_add_uint, 8)
    add_uint16 = functools.partialmethod(_add_uint, 16)
    add_uint32 = functools.partialmethod(_add_uint, 32)

    # writes an unsigned, arbitrarily big integer in a funny format where least
    # significant byte is last
    def add_big_uint(self, abs_value):
        assert abs_value >= 0

        result = bytearray()
        while abs_value != 0:
            result.append(abs_value & 0xff)
            abs_value >>= 8
        result.reverse()

        self.add_uint32(len(result))
        self.byte_array.extend(result)

    def add_byte(self, byte):
        if isinstance(byte, int):
            self.byte_array.append(byte)
        else:
            assert len(byte) == 1
            self.byte_array.extend(byte)

    def write_string(self, string):
        utf8 = string.encode('utf-8')
        self.add_uint32(len(utf8))
        self.byte_array.extend(utf8)

    def set_lineno(self, lineno):
        if lineno != self.current_lineno:
            self.byte_array.extend(SET_LINENO)
            self.add_uint32(lineno)
            self.current_lineno = lineno


class _BytecodeWriter:

    def __init__(self, bytecode):
        self.bytecode = bytecode

        # the bytecode doesn't contain jump markers, and it instead jumps by
        # index, it turns out to be much easier to figure out the indexes
        # beforehand
        self.jumpmarker2index = {}

    def write_type(self, tybe):
        if tybe in objects.BUILTIN_TYPES.values():
            names = list(objects.BUILTIN_TYPES)
            self.bytecode.add_byte(TYPE_BUILTIN)
            self.bytecode.add_uint8(names.index(tybe.name))

        elif isinstance(tybe, objects.FunctionType):
            self.bytecode.add_byte(CREATE_FUNCTION)
            self.write_type(tybe.returntype)

            self.bytecode.add_uint8(len(tybe.argtypes))
            for argtype in tybe.argtypes:
                self.write_type(argtype)

        elif isinstance(tybe, objects.GeneratorType):
            self.bytecode.add_byte(TYPE_GENERATOR)
            self.write_type(tybe.item_type)

        elif tybe is None:
            self.bytecode.add_byte(TYPE_VOID)

        else:
            assert False, tybe      # pragma: no cover

    def write_op(self, op, varlists):
        self.bytecode.set_lineno(op.lineno)

        if isinstance(op, opcoder.StrConstant):
            self.bytecode.add_byte(STR_CONSTANT)
            self.bytecode.write_string(op.python_string)
            return

        if isinstance(op, opcoder.IntConstant):
            if op.python_int >= 0:
                self.bytecode.add_byte(NON_NEGATIVE_INT_CONSTANT)
                self.bytecode.add_big_uint(op.python_int)
            else:
                # currently this code never runs because -2 is parsed as the
                # prefix minus operator applied to the non-negative integer
                # constant 2, but i'm planning on adding an optimizer that
                # would output it as a thing that needs this code
                self.bytecode.add_byte(NEGATIVE_INT_CONSTANT)
                self.bytecode.add_big_uint(abs(op.python_int))
            return

        if isinstance(op, opcoder.BoolConstant):
            self.bytecode.add_byte(
                TRUE_CONSTANT if op.python_bool else FALSE_CONSTANT)
            return

        if isinstance(op, opcoder.CreateFunction):
            assert isinstance(op.functype, objects.FunctionType)
            self.write_type(op.functype)    # includes CREATE_FUNCTION
            self.bytecode.add_byte(1 if op.yields else 0)
            self.bytecode.write_string(op.name)

            _BytecodeWriter(self.bytecode).run(op.body_opcode, varlists)
            return

        if isinstance(op, opcoder.LookupVar):
            self.bytecode.add_byte(LOOKUP_VAR)
            self.bytecode.add_uint8(op.level)
            if isinstance(op.var, opcoder.ArgMarker):
                self.bytecode.add_uint16(op.var.index)
            else:
                assert isinstance(op.var, opcoder.VarMarker)
                self.bytecode.add_uint16(varlists[op.level].index(op.var))
            return

        if isinstance(op, opcoder.SetVar):
            self.bytecode.add_byte(SET_VAR)
            self.bytecode.add_uint8(op.level)
            self.bytecode.add_uint16(varlists[op.level].index(op.var))
            return

        if isinstance(op, opcoder.CallFunction):
            self.bytecode.add_byte(
                CALL_RETURNING_FUNCTION if op.returns_a_value
                else CALL_VOID_FUNCTION)
            self.bytecode.add_uint8(op.nargs)
            return

        if isinstance(op, opcoder.Return):
            self.bytecode.add_byte(VALUE_RETURN if op.returns_a_value
                                   else VOID_RETURN)
            return

        if isinstance(op, opcoder.JumpIf):
            self.bytecode.add_byte(JUMP_IF)
            self.bytecode.add_uint16(self.jumpmarker2index[op.marker])
            return

        elif isinstance(op, opcoder.LookupMethod):
            self.bytecode.add_byte(LOOKUP_METHOD)
            self.write_type(op.type)
            self.bytecode.add_uint16(op.indeks)
            return

        elif isinstance(op, opcoder.StrJoin):
            self.bytecode.add_byte(STR_JOIN)
            self.bytecode.add_uint16(op.how_many_parts)
            return

        if isinstance(op, opcoder.JumpMarker):
            # already handled in run()
            return

        simple_things = [
            (opcoder.PopOne, POP_ONE),
            (opcoder.Yield, YIELD),
            (opcoder.BoolNegation, BOOL_NEGATION),
            (opcoder.DidntReturnError, DIDNT_RETURN_ERROR),
            (opcoder.Plus, PLUS),
            (opcoder.Minus, MINUS),
            (opcoder.PrefixMinus, PREFIX_MINUS),
            (opcoder.Times, TIMES),
            #(opcoder.Divide, DIVIDE),
            (opcoder.Equal, EQUAL),
        ]

        for klass, byte in simple_things:
            if isinstance(op, klass):
                self.bytecode.add_byte(byte)
                return

        assert False, op        # pragma: no cover

    # don't call this more than once because jumpmarker2index
    def run(self, opcode, varlists):
        # using += would mutate the argument and cause confusing things because
        # python is awesome
        varlists = varlists + [opcode.local_vars]

        i = 0       # no, enumerate() does not work for this
        for op in opcode.ops:
            if isinstance(op, opcoder.JumpMarker):
                self.jumpmarker2index[op] = i
            else:
                i += 1

        self.bytecode.add_uint16(len(opcode.local_vars))
        for op in opcode.ops:
            self.write_op(op, varlists)
        self.bytecode.add_byte(END_OF_BODY)

    def write_export_section(self, exports):
        # _BytecodeReader reads this with seek
        export_beginning = len(self.bytecode.byte_array)

        assert isinstance(exports, collections.OrderedDict)
        self.bytecode.add_byte(EXPORT_SECTION)
        self.bytecode.add_uint32(len(exports))
        for name, tybe in exports.items():
            self.bytecode.write_string(name)
            self.write_type(tybe)

        self.bytecode.add_uint32(export_beginning)


def create_bytecode(opcode, exports):
    output = _ByteCode()
    output.byte_array.extend(b'asda')

    # the built-in varlist is None because all builtins are implemented
    # as ArgMarkers, so they don't need a varlist
    writer = _BytecodeWriter(output)
    writer.run(opcode, [None])
    writer.write_export_section(exports)
    return output.byte_array


# can't read anything, but can read the exports section
class _BytecodeReader:

    def __init__(self, file):
        self.file = file

    # errors on unexpected eof
    def _read(self, size):
        result = self.file.read(size)
        if len(result) != size:
            raise common.CompileError(
                "the bytecode file %s seems to be truncated" % self.file.name)
        return result

    def _read_uint(self, size):
        assert size % 8 == 0 and 0 < size <= 64, size
        result = 0
        for offset in range(0, size, 8):
            result |= self._read(1)[0] << offset
        return result

    read_uint8 = functools.partialmethod(_read_uint, 8)
    read_uint32 = functools.partialmethod(_read_uint, 32)

    def read_string(self):
        length = self.read_uint32()
        utf8 = self._read(length)
        return utf8.decode('utf-8')

    def read_type(self, *, name_hint='<anonymous>'):
        byte = self._read(1)
        [byte_int] = byte

        if byte == TYPE_BUILTIN:
            index = self.read_uint8()
            return list(objects.BUILTIN_TYPES.values())[index]

        if byte == CREATE_FUNCTION:
            returntype = self.read_type()
            nargs = self.read_uint8()
            argtypes = [self.read_type() for junk in range(nargs)]
            return objects.FunctionType(name_prefix, argtypes, returntype)

        if byte == TYPE_GENERATOR:
            item_type = self.read_type()
            return objects.GeneratorType(item_type)

        raise common.CompileError(
            "the file %s contains invalid type byte %#02x" % byte_int)

    def check_asda_part(self):
        if self.file.read(4) != b'asda':
            raise common.CompileError(
                ("the file %s doesn't seem like an asda bytecode file"
                 % self.file.name))

    def read_export_section(self):
        self.file.seek(-32//8, io.SEEK_END)
        new_seek_pos = self.read_uint32()
        self.file.seek(new_seek_pos)
        if self._read(1) != EXPORT_SECTION:
            raise common.CompileError(
                ("the file %s seems to have garbage at the end or something"
                 % self.file.name))

        result = {}
        how_many = self.read_uint32()
        for junk in range(how_many):
            name = self.read_string()
            tybe = self.read_type()
            result[name] = tybe

        return result


# initial position of the file should be at the beginning
def read_exports(bytecodefile):
    reader = _BytecodeReader(bytecodefile)
    reader.check_asda_part()
    return reader.read_export_section()
