import collections
import functools
import io
import os

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
LOOKUP_ATTRIBUTE = b'.'
LOOKUP_FROM_MODULE = b'm'
CALL_FUNCTION = b'('
CALL_CONSTRUCTOR = b')'
STR_JOIN = b'j'
POP_ONE = b'P'
VOID_RETURN = b'r'
VALUE_RETURN = b'R'
DIDNT_RETURN_ERROR = b'd'
THROW = b't'
YIELD = b'Y'
BOOL_NEGATION = b'!'
JUMP_IF = b'J'
JUMP = b'K'
END_OF_BODY = b'E'

PLUS = b'+'
MINUS = b'-'
PREFIX_MINUS = b'_'
TIMES = b'*'
# DIVIDE = b'/'
EQUAL = b'='

ADD_ERROR_HANDLER = b'h'
REMOVE_ERROR_HANDLER = b'H'

PUSH_FINALLY_STATE_OK = b'3'
PUSH_FINALLY_STATE_ERROR = b'4'
PUSH_FINALLY_STATE_VOID_RETURN = b'5'
PUSH_FINALLY_STATE_VALUE_RETURN = b'6'
PUSH_FINALLY_STATE_JUMP = b'7'

APPLY_FINALLY_STATE = b'A'
DISCARD_FINALLY_STATE = b'D'


# these are used when bytecoding a type
TYPE_BUILTIN = b'b'
TYPE_FUNCTION = b'f'
TYPE_VOID = b'v'
TYPE_FROM_LIST = b'l'

IMPORT_SECTION = b'i'
EXPORT_SECTION = b'e'
TYPE_LIST_SECTION = b'y'


def _bit_storing_size(n):
    """Returns the number of bytes needed for storing n bits.

    >>> _bit_storing_size(16)
    2
    >>> _bit_storing_size(17)
    3
    """
    return -((-n) // 8)


class _ByteCode:

    def __init__(self):
        self.byte_array = bytearray()
        self.current_lineno = 1

    # clears the byte array
    def get_bytes(self):
        result = bytes(self.byte_array)
        self.byte_array.clear()
        return result

    # writes an unsigned little-endian integer
    def _add_uint(self, bits, number):
        r"""
        >>> bc = _ByteCode()
        >>> bc.add_uint16(1)
        >>> bc.get_bytes()
        b'\x01\x00'
        """
        assert bits % 8 == 0 and 0 < bits <= 64, bits
        try:
            self.byte_array.extend(number.to_bytes(bits // 8, 'little'))
        except OverflowError:
            raise common.CompileError(
                "this number does not fit in an unsigned %d-bit integer: %d"
                % (bits, number))

    add_uint8 = functools.partialmethod(_add_uint, 8)
    add_uint16 = functools.partialmethod(_add_uint, 16)
    add_uint32 = functools.partialmethod(_add_uint, 32)

    def add_big_uint(self, abs_value):
        assert abs_value >= 0
        size = _bit_storing_size(abs_value.bit_length())
        self.add_uint32(size)
        self.byte_array.extend(abs_value.to_bytes(size, 'little'))

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

    def __init__(self, bytecode, compilation):
        self.bytecode = bytecode
        self.compilation = compilation

        # the bytecode doesn't contain jump markers, and it instead jumps by
        # index, it turns out to be much easier to figure out the indexes
        # beforehand
        self.jumpmarker2index = {}

        # when the interpreter imports the bytecode file, it creates things
        # that represent these types, and looks up these types by index
        self.type_list = []

    def _create_subwriter(self):
        return _BytecodeWriter(self.bytecode, self.compilation)

    def write_path(self, path):
        relative2 = self.compilation.compiled_path.parent
        relative_path = common.relpath(path, relative2)
        # os.path.normcase replaces / with \ on windows, but we actually want /
        # for this to make the compiled bytecodes cross-platform
        #
        # TODO: delete normcase and assert that the path is lowercase, because
        #       it is lowercased elsewhere
        self.bytecode.write_string(
            os.path.normcase(str(relative_path)).replace(os.sep, '/'))

    def write_type(self, tybe, *, allow_void=False):
        if tybe in self.type_list:
            self.bytecode.add_byte(TYPE_FROM_LIST)
            self.bytecode.add_uint16(self.type_list.index(tybe))

        elif tybe in objects.BUILTIN_TYPES.values():
            names = list(objects.BUILTIN_TYPES)
            self.bytecode.add_byte(TYPE_BUILTIN)
            self.bytecode.add_uint8(names.index(tybe.name))

        elif isinstance(tybe, objects.FunctionType):
            self.bytecode.add_byte(TYPE_FROM_LIST)
            self.bytecode.add_uint16(len(self.type_list))
            self.type_list.append(tybe)

        elif tybe is None:
            assert allow_void
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
            self.bytecode.add_byte(CREATE_FUNCTION)
            self.write_type(op.functype)
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
            self.bytecode.add_byte(CALL_FUNCTION)
            self.bytecode.add_uint8(op.nargs)       # TODO: bigger than uint8
            return

        if isinstance(op, opcoder.CallConstructor):
            self.bytecode.add_byte(CALL_CONSTRUCTOR)
            self.write_type(op.tybe)
            self.bytecode.add_uint8(op.nargs)   # TODO: bigger than uint8
            return

        if isinstance(op, opcoder.Return):
            self.bytecode.add_byte(VALUE_RETURN if op.returns_a_value
                                   else VOID_RETURN)
            return

        if isinstance(op, (opcoder.Jump, opcoder.JumpIf)):
            if isinstance(op, opcoder.Jump):
                self.bytecode.add_byte(JUMP)
            elif isinstance(op, opcoder.JumpIf):
                self.bytecode.add_byte(JUMP_IF)
            else:  # pragma: no cover
                raise RuntimeError
            self.bytecode.add_uint16(self.jumpmarker2index[op.marker])
            return

        if isinstance(op, opcoder.LookupAttribute):
            self.bytecode.add_byte(LOOKUP_ATTRIBUTE)
            self.write_type(op.type)
            self.bytecode.add_uint16(op.indeks)
            return

        if isinstance(op, opcoder.StrJoin):
            self.bytecode.add_byte(STR_JOIN)
            self.bytecode.add_uint16(op.how_many_parts)
            return

        if isinstance(op, opcoder.JumpMarker):
            # already handled in run()
            return

        if isinstance(op, opcoder.LookupFromModule):
            self.bytecode.add_byte(LOOKUP_FROM_MODULE)
            self.bytecode.add_uint16(
                self.compilation.imports.index(op.compilation))
            self.bytecode.add_uint16(op.indeks)
            return

        if isinstance(op, opcoder.AddErrorHandler):
            self.bytecode.add_byte(ADD_ERROR_HANDLER)
            self.bytecode.add_uint16(self.jumpmarker2index[op.jumpto_marker])
            self.write_type(op.errortype)
            self.bytecode.add_uint16(
                varlists[op.errorvarlevel].index(op.errorvar))
            return

        if isinstance(op, opcoder.PushFinallyStateReturn):
            self.bytecode.add_byte(PUSH_FINALLY_STATE_VALUE_RETURN
                                   if op.returns_a_value else
                                   PUSH_FINALLY_STATE_VOID_RETURN)
            return

        if isinstance(op, opcoder.PushFinallyStateJump):
            self.bytecode.add_byte(PUSH_FINALLY_STATE_JUMP)
            self.bytecode.add_uint16(self.jumpmarker2index[op.index])
            return

        simple_things = [
            (opcoder.PopOne, POP_ONE),
            (opcoder.BoolNegation, BOOL_NEGATION),
            (opcoder.DidntReturnError, DIDNT_RETURN_ERROR),
            (opcoder.Plus, PLUS),
            (opcoder.Minus, MINUS),
            (opcoder.PrefixMinus, PREFIX_MINUS),
            (opcoder.Times, TIMES),
            # (opcoder.Divide, DIVIDE),
            (opcoder.Equal, EQUAL),
            (opcoder.RemoveErrorHandler, REMOVE_ERROR_HANDLER),
            (opcoder.PushFinallyStateOk, PUSH_FINALLY_STATE_OK),
            (opcoder.PushFinallyStateError, PUSH_FINALLY_STATE_ERROR),
            (opcoder.DiscardFinallyState, DISCARD_FINALLY_STATE),
            (opcoder.ApplyFinallyState, APPLY_FINALLY_STATE),
            (opcoder.Throw, THROW),
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

    # use this after run()
    def write_type_list(self):
        self.bytecode.add_byte(TYPE_LIST_SECTION)
        self.bytecode.add_uint16(len(self.type_list))
        for tybe in self.type_list:
            if isinstance(tybe, objects.FunctionType):
                self.bytecode.add_byte(CREATE_FUNCTION)
                self.write_type(tybe.returntype, allow_void=True)

                self.bytecode.add_uint8(len(tybe.argtypes))
                for argtype in tybe.argtypes:
                    self.write_type(argtype)

            else:   # pragma: no cover
                raise NotImplementedError(repr(tybe))

    # this can be used to write either one of the two import sections
    def write_import_section(self, paths):
        self.bytecode.add_byte(IMPORT_SECTION)
        self.bytecode.add_uint16(len(paths))
        for path in paths:
            self.write_path(path)

    def write_export_section(self, exports):
        assert isinstance(exports, collections.OrderedDict)
        self.bytecode.add_byte(EXPORT_SECTION)
        self.bytecode.add_uint32(len(exports))
        for name, tybe in exports.items():
            self.bytecode.write_string(name)
            self.write_type(tybe)


# structure of a bytecode file:
#   1.  the bytes b'asda\xA5\xDA'  (note how 5 looks like S, lol)
#   2.  source path string, relative to the dirname of the compiled path
#   3.  first import section: compiled file paths for the interpreter
#   4.  list of types used in the opcode
#   5.  opcode
#   6.  list of imports, source file paths, for the compiler
#   7.  list of exports, names and types, for the compiler
#   8.  number of bytes before part 4, as an uint32.
#       The compiler uses this to efficiently read imports and exports.
#
# all paths are relative to the bytecode file's directory and have '/' as
# the separator
def create_bytecode(compilation, opcode):
    output = _ByteCode()
    writer = _BytecodeWriter(output, compilation)

    writer.write_path(compilation.source_path)
    source_path_bytes = output.get_bytes()

    writer.write_import_section(
        [impcomp.compiled_path for impcomp in compilation.imports])
    import_section_bytes = output.get_bytes()

    # the built-in varlist is None because all builtins are implemented
    # as ArgMarkers, so they don't need a varlist
    writer.run(opcode, [None])
    opcode_bytes = output.get_bytes()

    writer.write_type_list()
    type_list_bytes = output.get_bytes()

    result = (b'asda\xA5\xDA' + source_path_bytes + import_section_bytes +
              type_list_bytes + opcode_bytes)
    seek_index = len(result)   # _BytecodeReader reads this with seek
    output.add_uint32(seek_index)
    seek_index_u32 = output.get_bytes()

    writer.write_import_section(
        [impcomp.source_path for impcomp in compilation.imports])
    writer.write_export_section(compilation.export_types)
    return result + output.get_bytes() + seek_index_u32


class RecompileFixableError(Exception):
    """Raised for errors that can be fixed by recompiling a file.

    They happen when reading bytecode files, not when writing them.
    """

    def __init__(self, compilation, message):
        self.compilation = compilation
        self.message = message

    def __str__(self):
        return '%s (%r)' % (self.message, self.compilation)


class _BytecodeReader:

    def __init__(self, compilation, file):
        self.compilation = compilation
        self.file = file

    def error(self, message):
        raise RecompileFixableError(self.compilation, message)

    # errors on unexpected eof
    def _read(self, size):
        result = self.file.read(size)
        if len(result) != size:
            self.error("the bytecode file seems to be truncated")
        return result

    def _read_uint(self, size):
        assert size % 8 == 0 and 0 < size <= 64, size
        return int.from_bytes(self._read(size // 8), 'little')

    read_uint8 = functools.partialmethod(_read_uint, 8)
    read_uint16 = functools.partialmethod(_read_uint, 16)
    read_uint32 = functools.partialmethod(_read_uint, 32)

    def read_string(self):
        length = self.read_uint32()
        utf8 = self._read(length)

        try:
            return utf8.decode('utf-8')
        except UnicodeDecodeError:
            bad = utf8.decode('utf-8', errors='replace')
            self.error("the file contains a string of invalid utf-8: " + bad)

    def read_path(self):
        relative_path = self.read_string().replace('/', os.sep)
        relative_to = self.compilation.compiled_path.parent
        assert relative_to.is_absolute()
        return common.resolve_dotdots(relative_to / relative_path)

    # TODO: module types?
    def read_type(self, *, name_hint='<unknown name>'):
        byte = self._read(1)

        if byte == TYPE_BUILTIN:
            index = self.read_uint8()
            return list(objects.BUILTIN_TYPES.values())[index]

        if byte == CREATE_FUNCTION:
            returntype = self.read_type()
            nargs = self.read_uint8()
            argtypes = [self.read_type() for junk in range(nargs)]
            return objects.FunctionType(argtypes, returntype)

        if byte == TYPE_GENERATOR:
            item_type = self.read_type()
            return objects.GeneratorType(item_type)

        if byte == TYPE_VOID:
            return None

        self.error("invalid type byte %r" % byte)

    def check_asda_part(self):
        if self.file.read(4) != b'asda':
            self.error("the file is not an asda bytecode file")

    def seek_to_end_sections(self):
        self.file.seek(-32//8, io.SEEK_END)
        new_seek_pos = self.read_uint32()
        self.file.seek(new_seek_pos)

    # returns a list of absolute source file paths
    # TODO: can this return compilation objects instead?
    def read_second_import_section(self):
        if self._read(1) != IMPORT_SECTION:
            self.error(
                "the file doesn't seem to have a valid second import section")

        result = []
        how_many = self.read_uint16()
        for junk in range(how_many):
            result.append(self.read_path())
        return result

    def read_export_section(self):
        if self._read(1) != EXPORT_SECTION:
            self.error("the file doesn't seem to have a valid export section")

        result = collections.OrderedDict()
        how_many = self.read_uint32()
        for junk in range(how_many):
            name = self.read_string()
            tybe = self.read_type(name_hint=name)
            result[name] = tybe
        return result


def read_imports_and_exports(compilation):
    with compilation.messager.indented(3, "Reading the compiled file..."):
        with compilation.compiled_path.open('rb') as file:
            reader = _BytecodeReader(compilation, file)
            reader.check_asda_part()
            reader.seek_to_end_sections()
            imports = reader.read_second_import_section()
            exports = reader.read_export_section()
            compilation.messager(4, "Imported files: " + (
                ', '.join(map(common.path_string, imports)) or '(none)'))

    return (imports, exports)
