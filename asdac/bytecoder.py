import functools

from . import common, opcoder


CREATE_FUNCTION = b'f'
CREATE_GENERATOR_FUNCTION = b'g'
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'
INT_CONSTANT = b'1'
TRUE_CONSTANT = b'T'
FALSE_CONSTANT = b'F'
CALL_VOID_FUNCTION = b'('
CALL_RETURNING_FUNCTION = b')'
POP_ONE = b'P'
VOID_RETURN = b'r'
VALUE_RETURN = b'R'
NEGATION = b'!'
JUMP_IF = b'J'
END_OF_BODY = b'E'


class _BytecodeWriter:

    def __init__(self, output):
        self.output = output

        # the bytecode doesn't contain jump markers, and it instead jumps by
        # index, it turns out to be much easier to figure out the indexes
        # beforehand
        self.jumpmarker2index = {}

    def _write_uint(self, size, number):
        assert size % 8 == 0 and 0 < size <= 64, size
        assert number >= 0
        if number >= 2**size:
            raise common.CompileError(
                "this number does not fit in an unsigned %d-bit integer: %d"
                % (size, number))

        self.output.extend((number >> offset) & 0xff
                           for offset in range(0, size, 8))

    write_uint8 = functools.partialmethod(_write_uint, 8)
    write_uint16 = functools.partialmethod(_write_uint, 16)
    write_uint32 = functools.partialmethod(_write_uint, 32)
    write_uint64 = functools.partialmethod(_write_uint, 64)

    def write_string(self, string):
        utf8 = string.encode('utf-8')
        self.write_uint32(len(utf8))
        self.output.extend(utf8)

    def write_type(self, type_):
        # FIXME
        self.write_string(type_.name)

    def write_op(self, op):
        if isinstance(op, opcoder.StrConstant):
            self.output.extend(STR_CONSTANT)
            self.write_string(op.python_string)

        # TODO: IntConstant

        elif isinstance(op, opcoder.BoolConstant):
            self.output.extend(
                TRUE_CONSTANT if op.python_bool else FALSE_CONSTANT)

        elif isinstance(op, opcoder.CreateFunction):
            self.output.extend(CREATE_GENERATOR_FUNCTION if op.is_generator
                               else CREATE_FUNCTION)
            self.write_string(op.name)
            _BytecodeWriter(self.output).run(op.body_opcode)

        elif isinstance(op, opcoder.LookupVar):
            self.output.extend(LOOKUP_VAR)
            self.write_uint8(op.level)
            self.write_uint16(op.var)

        elif isinstance(op, opcoder.SetVar):
            self.output.extend(SET_VAR)
            self.write_uint8(op.level)
            self.write_uint16(op.var)

        elif isinstance(op, opcoder.CallFunction):
            self.output.extend(CALL_RETURNING_FUNCTION if op.returns_a_value
                               else CALL_VOID_FUNCTION)
            self.write_uint8(op.nargs)

        elif isinstance(op, opcoder.PopOne):
            self.output.extend(POP_ONE)

        elif isinstance(op, opcoder.Return):
            self.output.extend(VALUE_RETURN if op.returns_a_value
                               else VOID_RETURN)

        elif isinstance(op, opcoder.Negation):
            self.output.extend(NEGATION)

        elif isinstance(op, opcoder.JumpIf):
            self.output.extend(JUMP_IF)
            self.write_uint16(self.jumpmarker2index[op.marker])

        elif isinstance(op, opcoder.JumpMarker):
            # already handled in run()
            pass

        else:
            assert False, op

    # don't call this more than once
    def run(self, opcode):
        i = 0
        for op in opcode.ops:
            if isinstance(op, opcoder.JumpMarker):
                self.jumpmarker2index[op] = i
            else:
                i += 1

        self.write_uint16(len(opcode.local_vars))
        for op in opcode.ops:
            self.write_op(op)
        self.output.extend(END_OF_BODY)


def create_bytecode(opcode):
    output = bytearray()
    _BytecodeWriter(output).run(opcode)
    return output
