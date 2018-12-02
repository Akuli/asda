import functools

from . import common, cooked_ast


CREATE_FUNCTION = b'f'
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'
INT_CONSTANT = b'1'
CALL_VOID_FUNCTION = b'('
CALL_RETURNING_FUNCTION = b')'
POP_ONE = b'P'
VOID_RETURN = b'r'
VALUE_RETURN = b'R'
NEGATION = b'!'
JUMP_IF = b'J'
END_OF_BODY = b'E'


def _uint2bytes(size, number):
    assert size % 8 == 0 and 0 < size <= 64, size
    assert number >= 0
    if number >= 2**size:
        raise common.CompileError(
            "this number does not fit in an unsigned %d-bit integer: %d"
            % (size, number))

    return bytes([(number >> offset) & 0xff
                  for offset in range(0, size, 8)])


class _BytecodeWriter:

    def __init__(self, output, parent_writer):
        self.output = output
        self.parent_writer = parent_writer
        if parent_writer is None:
            self.level = 0
        else:
            self.level = parent_writer.level + 1

        self.local_vars = {}     # {name: index}
        self.opcode_number = 0

    def _write_uint(self, size, number):
        self.output.extend(_uint2bytes(size, number))

    write_uint8 = functools.partialmethod(_write_uint, 8)
    write_uint16 = functools.partialmethod(_write_uint, 16)
    write_uint32 = functools.partialmethod(_write_uint, 32)
    write_uint64 = functools.partialmethod(_write_uint, 64)

    def write_opcode(self, op):
        assert len(op) == 1
        self.output.extend(op)
        self.opcode_number += 1

    def write_string(self, string):
        utf8 = string.encode('utf-8')
        self.write_uint32(len(utf8))
        self.output.extend(utf8)

    def do_type(self, type_):
        # FIXME
        self.write_string(type_.name)

    def do_function_call(self, call):
        self.do_expression(call.function)
        for arg in call.args:
            self.do_expression(arg)
        self.write_opcode(CALL_VOID_FUNCTION if call.type is None
                          else CALL_RETURNING_FUNCTION)
        self.write_uint8(len(call.args))

    def do_expression(self, expression):
        if isinstance(expression, cooked_ast.StrConstant):
            self.write_opcode(STR_CONSTANT)
            self.write_string(expression.python_string)

        elif isinstance(expression, cooked_ast.IntConstant):
            self.write_opcode(INT_CONSTANT)
            # TODO: how about bignums and negatives and stuff?
            self.write_uint64(expression.python_int)

        elif isinstance(expression, cooked_ast.CallFunction):
            self.do_function_call(expression)

        elif isinstance(expression, cooked_ast.CreateFunction):
            self.write_opcode(CREATE_FUNCTION)
            self.write_string(expression.name)
            writer = _BytecodeWriter(self.output, self)
            for index, (argname, argtype) in enumerate(expression.args):
                writer.local_vars[argname] = index
            writer.do_body(expression.body)

        elif isinstance(expression, cooked_ast.LookupVar):
            self.write_opcode(LOOKUP_VAR)
            self.write_uint8(expression.level)

            level_difference = self.level - expression.level
            assert level_difference >= 0

            writer = self
            for lel in range(level_difference):
                writer = writer.parent_writer
            self.write_uint16(writer.local_vars[expression.varname])

        else:
            assert False, expression

    def do_statement(self, statement):
        if isinstance(statement, cooked_ast.CreateLocalVar):
            self.do_expression(statement.initial_value)
            self.write_opcode(SET_VAR)
            self.write_uint16(self.local_vars[statement.varname])
        elif isinstance(statement, cooked_ast.CallFunction):
            self.do_function_call(statement)
            if statement.type is not None:
                # not a void function, ignore return value
                self.write_opcode(POP_ONE)
        elif isinstance(statement, cooked_ast.SetVar):
            # FIXME: nonlocal variables???
            self.do_expression(statement.value)
            self.write_opcode(SET_VAR)
            self.write_uint16(self.local_vars[statement.varname])
        elif isinstance(statement, cooked_ast.VoidReturn):
            self.write_opcode(VOID_RETURN)
        elif isinstance(statement, cooked_ast.ValueReturn):
            self.do_expression(statement.value)
            self.write_opcode(VALUE_RETURN)
        elif isinstance(statement, cooked_ast.If):
            self.do_expression(statement.condition)
            self.write_opcode(NEGATION)
            self.write_opcode(JUMP_IF)
            jump_target_index = len(self.output)
            for substatement in statement.body:
                self.do_statement(substatement)
            self.output[jump_target_index:jump_target_index] = _uint2bytes(
                16, self.opcode_number)
        else:
            assert False, statement

    def _var_creating_statements(self, statement_list):
        for statement in statement_list:
            if isinstance(statement, cooked_ast.CreateLocalVar):
                yield statement
            elif isinstance(statement, cooked_ast.If):
                yield from self._var_creating_statements(statement.body)

    def do_body(self, statements):
        assert iter(statements) is not statements, (
            "statements must not be an iterator because this thing needs to "
            "loop over it twice")

        for statement in self._var_creating_statements(statements):
            assert statement.varname not in self.local_vars
            self.local_vars[statement.varname] = len(self.local_vars)

        self.write_uint16(len(self.local_vars))
        for statement in statements:
            self.do_statement(statement)
        self.output.extend(END_OF_BODY)


def create_bytecode(cooked):
    builtin_writer = _BytecodeWriter(None, None)
    builtin_writer.local_vars.update({
        'print': 0,
        'TRUE': 1,
        'FALSE': 2,
    })
    output = bytearray()
    _BytecodeWriter(output, builtin_writer).do_body(cooked)
    return output
