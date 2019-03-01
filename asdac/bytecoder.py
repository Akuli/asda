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
IMPORT_SECTION = b'i'
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

    def __init__(self, bytecode, source_path, compiled_path):
        self.bytecode = bytecode
        self.source_path = source_path
        self.compiled_path = compiled_path

        # the bytecode doesn't contain jump markers, and it instead jumps by
        # index, it turns out to be much easier to figure out the indexes
        # beforehand
        self.jumpmarker2index = {}

    def _create_subwriter(self):
        return _BytecodeWriter(self.bytecode, self.source_path,
                               self.compiled_path)

    def write_path(self, path):
        relative2 = os.path.dirname(compiled_path)
        relative_path = os.path.relpath(path, relative2)
        self.bytecode.write_string(relative_path.replace(os.sep, '/'))

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

            self._create_subwriter().run(op.body_opcode, varlists)
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

    # imports is a list of (source, compiled) pairs
    # this can be used to write either one of the two import sections
    def write_import_section(self, imports):
        self.bytecode.add_byte(IMPORT_SECTION)
        self.bytecode.add_uint32(len(imports))
        for path in imports:
            self.write_path(path)

    def write_export_section(self, exports):
        assert isinstance(exports, collections.OrderedDict)
        self.bytecode.add_byte(EXPORT_SECTION)
        self.bytecode.add_uint32(len(exports))
        for name, tybe in exports.items():
            self.bytecode.write_string(name)
            self.write_type(tybe)

    # imports is a list of source file paths
    # exports is a dict with names as keys and types as values
    def write_end_import_export_sections(self, imports, exports):
        # _BytecodeReader reads this with seek
        seek_index = len(self.bytecode.byte_array)
        self.write_import_section(imports)
        self.write_export_section(exports)
        self.bytecode.add_uint32(seek_index)


# structure of a bytecode file:
#   1.  the bytes b'asda'
#   2.  list of imports, bytecode file paths, for the interpreter
#   3.  the actual bytecode
#   4.  list of imports, source file paths, for the compiler
#   5.  list of exports, names and types, for the compiler
#   6.  number of bytes in parts 1, 2 and 3, as an uint32
#       the compiler uses this to efficiently read exports and imports
#
# all paths are relative to the bytecode file's directory and have '/' as
# the separator
def create_bytecode(source_path, compiled_path, opcode, imports, exports):
    output = _ByteCode()
    output.byte_array.extend(b'asda')

    writer = _BytecodeWriter(output, source_path, compiled_path)
    writer.write_import_section([compiled for source, compiled in imports])

    # the built-in varlist is None because all builtins are implemented
    # as ArgMarkers, so they don't need a varlist
    writer.run(opcode, [None])

    writer.write_import_section([source for source, compiled in imports])
    writer.write_export_section(exports)
    return output.byte_array


class RecompileFixableError(Exception):
    """Raised for errors that can be fixed by recompiling a file.

    They happen when reading bytecode files, not when writing them. The file
    that contains the problem is the_error.compiled_path, and the file that
    should be recompiled is the_error.source_path. A user-displayable
    description is in the_error.message.
    """

    def __init__(self, source_path, compiled_path, message):
        self.source_path = source_path
        self.compiled_path = compiled_path
        self.message = message

    def __str__(self):
        return '%s (%s --> %s)' % (self.message, self.source_path,
                                   self.compiled_path)


# can't read anything, but can read the exports section
class _BytecodeReader:

    def __init__(self, source_path, compiled_path, file):
        self.source_path = source_path
        self.compiled_path = compiled_path
        self.file = file

    def error(self, message):
        raise RecompileFixableError(self.source_path, self.compiled_path,
                                    message)

    # errors on unexpected eof
    def _read(self, size):
        result = self.file.read(size)
        if len(result) != size:
            self.error("the bytecode file seems to be truncated")
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
        if len(utf8) != length:
            self.error("unexpected end of file when reading a string")

        try:
            return utf8.decode('utf-8')
        except UnicodeDecodeError:
            bad = utf8.decode('utf-8', errors='replace')
            self.error("the file contains a string of invalid utf-8: " + bad)

    def read_path(self):
        relative_path = self.read_string().replace('/', os.sep)
        relative_to = os.path.dirname(self.compiled_path)
        return os.path.join(relative_to, relative_path)

    def read_type(self, *, name_hint='<unknown name>'):
        byte = self._read(1)
        [byte_int] = byte

        if byte == TYPE_BUILTIN:
            index = self.read_uint8()
            return list(objects.BUILTIN_TYPES.values())[index]

        if byte == CREATE_FUNCTION:
            returntype = self.read_type()
            nargs = self.read_uint8()
            argtypes = [self.read_type() for junk in range(nargs)]
            return objects.FunctionType(name_hint, argtypes, returntype)

        if byte == TYPE_GENERATOR:
            item_type = self.read_type()
            return objects.GeneratorType(item_type)

        self.error("invalid type byte %#02x" % byte_int)

    def check_asda_part(self):
        if self.file.read(4) != b'asda':
            self.error("the file is not an asda bytecode file")

    def seek_to_import_section_beginning(self):
        self.file.seek(-32//8, io.SEEK_END)
        new_seek_pos = self.read_uint32()
        self.file.seek(new_seek_pos)

    # returns a list of absolute source file paths
    def read_import_section(self):
        if self._read(1) != IMPORT_SECTION:
            self.error(
                "the file doesn't seem to have a valid second import section")

        result = []
        how_many = self.read_uint32()
        for junk in range(how_many):
            source_path = self.read_path()
            compiled_path = self.read_path()
            result.append((source_path, compiled_path))
        return result

    def read_export_section(self):
        if self._read(1) != EXPORT_SECTION:
            self.error("the file doesn't seem to have a valid export section")

        result = {}
        how_many = self.read_uint32()
        for junk in range(how_many):
            name = self.read_string()
            tybe = self.read_type(name_hint=name)
            result[name] = tybe
        return result

    def should_be_at_end(self):
        if self._read(1) != b'':
            self.error("the file seems to contain garbage at the end")


def read_imports_and_exports(source_path, compiled_path):
    with open(compiled_path, 'rb') as file:
        reader = _BytecodeReader(source_path, compiled_path, file)
        reader.check_asda_part()
        reader.seek_to_import_section_beginning()
        imports = reader.read_import_section()
        exports = reader.read_export_section()
        reader.should_be_at_end()

    return (imports, exports)
