import enum
import functools

from . import common, chef


class _MagicCodes(enum.Enum):
    CREATE_FUNCTION = b'f'
    LOOKUP_VAR = b'v'
    SET_VAR = b'V'
    STR_CONSTANT = b'"'
    INT_CONSTANT = b'1'
    CALL_FUNCTION = b'('


class _BytecodeWriter:

    def __init__(self, write_callback, parent_writer):
        self._write = write_callback
        self.parent_writer = parent_writer
        if parent_writer is None:
            self.level = 0
        else:
            self.level = parent_writer.level + 1

        self.local_vars = {}     # {name: index}

    def _write_uint(self, size, number):
        assert size % 8 == 0 and 0 < size <= 64, size
        assert number >= 0
        if number >= 2**size:
            raise common.CompileError(
                "this number does not fit in an unsigned %d-bit integer: %d"
                % (size, number))

        for offset in range(0, size, 8):
            self._write(bytes([(number >> offset) & 0xff]))

    write_uint8 = functools.partialmethod(_write_uint, 8)
    write_uint16 = functools.partialmethod(_write_uint, 16)
    write_uint32 = functools.partialmethod(_write_uint, 32)
    write_uint64 = functools.partialmethod(_write_uint, 64)

    def write_string(self, string):
        utf8 = string.encode('utf-8')
        self.write_uint32(len(utf8))
        self._write(utf8)

    def write_magic(self, code: _MagicCodes):
        self._write(code.value)

    def do_type(self, type_):
        # FIXME
        self.write_string(type_.name)

    def do_function_call(self, call):
        self.write_magic(_MagicCodes.CALL_FUNCTION)
        self.do_expression(call.function)
        self.write_uint8(len(call.args))
        for arg in call.args:
            self.do_expression(arg)

    def do_expression(self, expression):
        if isinstance(expression, chef.StrConstant):
            self.write_magic(_MagicCodes.STR_CONSTANT)
            self.write_string(expression.python_string)
        elif isinstance(expression, chef.IntConstant):
            self.write_magic(_MagicCodes.INT_CONSTANT)
            # TODO: how about bignums and negatives and stuff?
            self.write_uint64(expression.python_int)
        elif isinstance(expression, chef.CallFunction):
            self.do_function_call(expression)
        elif isinstance(expression, chef.LookupVar):
            self.write_magic(_MagicCodes.LOOKUP_VAR)
            self.write_uint8(expression.level)

            level_difference = self.level - expression.level
            assert level_difference >= 0

            writer = self
            for lel in range(level_difference):
                writer = writer.parent_writer
            self.write_uint16(writer.local_vars[expression.varname])
        else:
            assert False, expression

    def do_body(self, statements):
        assert iter(statements) is not statements, (
            "statements must not be an iterator because this thing needs to "
            "loop over it twice")
        assert not self.local_vars, "cannot call do_body() more than once"

        vartypes = {}
        for statement in statements:
            if isinstance(statement, chef.CreateLocalVar):
                assert statement.name not in self.local_vars
                self.local_vars[statement.name] = len(self.local_vars)
                vartypes[statement.name] = statement.initial_value.type

        self.write_uint16(len(self.local_vars))
        for name, index in self.local_vars.items():
            self.do_type(vartypes[name])
            self.write_uint16(index)

        for statement in statements:
            if isinstance(statement, chef.CreateLocalVar):
                self.write_magic(_MagicCodes.SET_VAR)
                self.write_uint16(self.local_vars[statement.name])
                self.do_expression(statement.initial_value)
            elif isinstance(statement, chef.CallFunction):
                self.do_function_call(statement)
            else:
                assert False, statement


def create_bytecode(cooked, write_callback):
    builtin_writer = _BytecodeWriter(None, None)
    builtin_writer.local_vars.update({
        'print': 0,
    })
    _BytecodeWriter(write_callback, builtin_writer).do_body(cooked)
