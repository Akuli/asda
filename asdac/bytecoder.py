import functools

from . import common, objects, opcoder


SET_LINENO = b'L'

CREATE_FUNCTION = b'f'     # also used when bytecoding a type
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'
INT_CONSTANT = b'1'
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
NEGATION = b'!'
JUMP_IF = b'J'
END_OF_BODY = b'E'

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

    # writes a signed little-endian integer in two's complement
    def _add_int(self, size, number):
        # https://en.wikipedia.org/wiki/Two%27s_complement
        if number >= 0:
            u_value = number
        else:
            u_value = 2**size - abs(number)

        self._add_uint(size, u_value)

    add_int64 = functools.partialmethod(_add_int, 64)

    add_uint8 = functools.partialmethod(_add_uint, 8)
    add_uint16 = functools.partialmethod(_add_uint, 16)
    add_uint32 = functools.partialmethod(_add_uint, 32)

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

        elif isinstance(op, opcoder.IntConstant):
            self.bytecode.add_byte(INT_CONSTANT)
            self.bytecode.add_int64(op.python_int)

        elif isinstance(op, opcoder.BoolConstant):
            self.bytecode.add_byte(
                TRUE_CONSTANT if op.python_bool else FALSE_CONSTANT)

        elif isinstance(op, opcoder.CreateFunction):
            assert isinstance(op.functype, objects.FunctionType)
            self.write_type(op.functype)    # includes CREATE_FUNCTION
            self.bytecode.add_byte(1 if op.yields else 0)
            self.bytecode.write_string(op.name)

            _BytecodeWriter(self.bytecode).run(op.body_opcode, varlists)

        elif isinstance(op, opcoder.LookupVar):
            self.bytecode.add_byte(LOOKUP_VAR)
            self.bytecode.add_uint8(op.level)
            if isinstance(op.var, opcoder.ArgMarker):
                self.bytecode.add_uint16(op.var.index)
            else:
                self.bytecode.add_uint16(varlists[op.level].index(op.var))

        elif isinstance(op, opcoder.SetVar):
            self.bytecode.add_byte(SET_VAR)
            self.bytecode.add_uint8(op.level)
            self.bytecode.add_uint16(varlists[op.level].index(op.var))

        elif isinstance(op, opcoder.CallFunction):
            self.bytecode.add_byte(
                CALL_RETURNING_FUNCTION if op.returns_a_value
                else CALL_VOID_FUNCTION)
            self.bytecode.add_uint8(op.nargs)

        elif isinstance(op, opcoder.PopOne):
            self.bytecode.add_byte(POP_ONE)

        elif isinstance(op, opcoder.Return):
            self.bytecode.add_byte(VALUE_RETURN if op.returns_a_value
                                            else VOID_RETURN)

        elif isinstance(op, opcoder.Yield):
            self.bytecode.add_byte(YIELD)

        elif isinstance(op, opcoder.Negation):
            self.bytecode.add_byte(NEGATION)

        elif isinstance(op, opcoder.JumpIf):
            self.bytecode.add_byte(JUMP_IF)
            self.bytecode.add_uint16(self.jumpmarker2index[op.marker])

        elif isinstance(op, opcoder.JumpMarker):
            # already handled in run()
            pass

        elif isinstance(op, opcoder.LookupMethod):
            self.bytecode.add_byte(LOOKUP_METHOD)
            self.write_type(op.type)
            self.bytecode.add_uint16(op.indeks)

        elif isinstance(op, opcoder.DidntReturnError):
            self.bytecode.add_byte(DIDNT_RETURN_ERROR)

        elif isinstance(op, opcoder.StrJoin):
            self.bytecode.add_byte(STR_JOIN)
            self.bytecode.add_uint16(op.how_many_parts)

        else:
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


def create_bytecode(opcode):
    output = _ByteCode()
    # the built-in varlist is None because all builtins are implemented
    # as ArgMarkers, so they don't need a varlist
    _BytecodeWriter(output).run(opcode, [None])
    return output.byte_array
