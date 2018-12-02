import functools

from . import common, cooked_ast


CREATE_FUNCTION = b'f'
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'
INT_CONSTANT = b'1'
CALL_FUNCTION = b'('
POP_ONE = b'P'
END_OF_BODY = b'E'


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

    def do_type(self, type_):
        # FIXME
        self.write_string(type_.name)

    def do_function_call(self, call):
        self.do_expression(call.function)
        for arg in call.args:
            self.do_expression(arg)
        self._write(CALL_FUNCTION)
        self.write_uint8(len(call.args))

    def do_expression(self, expression):
        if isinstance(expression, cooked_ast.StrConstant):
            self._write(STR_CONSTANT)
            self.write_string(expression.python_string)

        elif isinstance(expression, cooked_ast.IntConstant):
            self._write(INT_CONSTANT)
            # TODO: how about bignums and negatives and stuff?
            self.write_uint64(expression.python_int)

        elif isinstance(expression, cooked_ast.CallFunction):
            self.do_function_call(expression)

        elif isinstance(expression, cooked_ast.CreateFunction):
            self._write(CREATE_FUNCTION)
            self.write_string(expression.name)
            writer = _BytecodeWriter(self._write, self)
            for index, (argname, argtype) in enumerate(expression.args):
                writer.local_vars[argname] = index
            writer.do_body(expression.body)

        elif isinstance(expression, cooked_ast.LookupVar):
            self._write(LOOKUP_VAR)
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

        for statement in statements:
            if isinstance(statement, cooked_ast.CreateLocalVar):
                assert statement.varname not in self.local_vars
                self.local_vars[statement.varname] = len(self.local_vars)

        self.write_uint16(len(self.local_vars))

        for statement in statements:
            if isinstance(statement, cooked_ast.CreateLocalVar):
                self.do_expression(statement.initial_value)
                self._write(SET_VAR)
                self.write_uint16(self.local_vars[statement.varname])
            elif isinstance(statement, cooked_ast.CallFunction):
                self.do_function_call(statement)
                self._write(POP_ONE)
            elif isinstance(statement, cooked_ast.SetVar):
                # FIXME: nonlocal variables???
                self.do_expression(statement.value)
                self._write(SET_VAR)
                self.write_uint16(self.local_vars[statement.varname])
            else:
                assert False, statement

        self._write(END_OF_BODY)


def create_bytecode(cooked, write_callback):
    builtin_writer = _BytecodeWriter(None, None)
    builtin_writer.local_vars.update({
        'print': 0,
        'TRUE': 1,
        'FALSE': 2,
    })
    _BytecodeWriter(write_callback, builtin_writer).do_body(cooked)
