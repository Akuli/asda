import functools

from . import common, objects, opcoder


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


class _BytecodeWriter:

    def __init__(self, output):
        self.output = output

        # the bytecode doesn't contain jump markers, and it instead jumps by
        # index, it turns out to be much easier to figure out the indexes
        # beforehand
        self.jumpmarker2index = {}

    # writes an unsigned little-endian integer
    def _write_uint(self, size, number):
        assert size % 8 == 0 and 0 < size <= 64, size
        assert number >= 0
        if number >= 2**size:
            raise common.CompileError(
                "this number does not fit in an unsigned %d-bit integer: %d"
                % (size, number))

        self.output.extend((number >> offset) & 0xff
                           for offset in range(0, size, 8))

    # writes a signed little-endian integer in two's complement
    def _write_int(self, size, number):
        # https://en.wikipedia.org/wiki/Two%27s_complement
        if number >= 0:
            u_value = number
        else:
            u_value = 2**size - abs(number)

        self._write_uint(size, u_value)

    write_int64 = functools.partialmethod(_write_int, 64)

    write_uint8 = functools.partialmethod(_write_uint, 8)
    write_uint16 = functools.partialmethod(_write_uint, 16)
    write_uint32 = functools.partialmethod(_write_uint, 32)

    def write_string(self, string):
        utf8 = string.encode('utf-8')
        self.write_uint32(len(utf8))
        self.output.extend(utf8)

    def write_type(self, tybe):
        if tybe in objects.BUILTIN_TYPES.values():
            names = list(objects.BUILTIN_TYPES)
            self.output.extend(TYPE_BUILTIN)
            self.write_uint8(names.index(tybe.name))

        elif isinstance(tybe, objects.FunctionType):
            self.output.extend(CREATE_FUNCTION)
            self.write_type(tybe.returntype)

            self.write_uint8(len(tybe.argtypes))
            for argtype in tybe.argtypes:
                self.write_type(argtype)

        elif isinstance(tybe, objects.GeneratorType):
            self.output.extend(TYPE_GENERATOR)
            self.write_type(tybe.item_type)

        elif tybe is None:
            self.output.extend(TYPE_VOID)

        else:
            assert False, tybe      # pragma: no cover

    def write_op(self, op, varlists):
        if isinstance(op, opcoder.StrConstant):
            self.output.extend(STR_CONSTANT)
            self.write_string(op.python_string)

        elif isinstance(op, opcoder.IntConstant):
            self.output.extend(INT_CONSTANT)
            self.write_int64(op.python_int)

        elif isinstance(op, opcoder.BoolConstant):
            self.output.extend(
                TRUE_CONSTANT if op.python_bool else FALSE_CONSTANT)

        elif isinstance(op, opcoder.CreateFunction):
            assert isinstance(op.functype, objects.FunctionType)
            self.write_type(op.functype)    # includes CREATE_FUNCTION
            self.output.append(1 if op.yields else 0)
            self.write_string(op.name)

            body_varlists = varlists + [op.body_opcode.local_vars]
            _BytecodeWriter(self.output).run(op.body_opcode, body_varlists)

        elif isinstance(op, opcoder.LookupVar):
            self.output.extend(LOOKUP_VAR)
            self.write_uint8(op.level)
            if isinstance(op.var, opcoder.ArgMarker):
                self.write_uint16(op.var.index)
            else:
                self.write_uint16(varlists[op.level].index(op.var))

        elif isinstance(op, opcoder.SetVar):
            self.output.extend(SET_VAR)
            self.write_uint8(op.level)
            self.write_uint16(varlists[op.level].index(op.var))

        elif isinstance(op, opcoder.CallFunction):
            self.output.extend(CALL_RETURNING_FUNCTION if op.returns_a_value
                               else CALL_VOID_FUNCTION)
            self.write_uint8(op.nargs)

        elif isinstance(op, opcoder.PopOne):
            self.output.extend(POP_ONE)

        elif isinstance(op, opcoder.Return):
            self.output.extend(VALUE_RETURN if op.returns_a_value
                               else VOID_RETURN)

        elif isinstance(op, opcoder.Yield):
            self.output.extend(YIELD)

        elif isinstance(op, opcoder.Negation):
            self.output.extend(NEGATION)

        elif isinstance(op, opcoder.JumpIf):
            self.output.extend(JUMP_IF)
            self.write_uint16(self.jumpmarker2index[op.marker])

        elif isinstance(op, opcoder.JumpMarker):
            # already handled in run()
            pass

        elif isinstance(op, opcoder.LookupMethod):
            self.output.extend(LOOKUP_METHOD)
            self.write_type(op.type)
            self.write_uint16(op.indeks)

        elif isinstance(op, opcoder.DidntReturnError):
            self.output.extend(DIDNT_RETURN_ERROR)

        elif isinstance(op, opcoder.StrJoin):
            self.output.extend(STR_JOIN)

        else:
            assert False, op        # pragma: no cover

    # don't call this more than once
    def run(self, opcode, varlists):
        i = 0
        for op in opcode.ops:
            if isinstance(op, opcoder.JumpMarker):
                self.jumpmarker2index[op] = i
            else:
                i += 1

        self.write_uint16(len(opcode.local_vars))
        for op in opcode.ops:
            self.write_op(op, varlists)
        self.output.extend(END_OF_BODY)


def create_bytecode(opcode):
    output = bytearray()
    # the built-in varlist is None because all builtins are implemented
    # as ArgMarkers, so they don't need a varlist
    _BytecodeWriter(output).run(opcode, [None, opcode.local_vars])
    return output
