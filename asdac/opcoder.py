from collections import namedtuple

from . import cooked_ast


# debugging tip: pprint.pprint(opcode.ops)
class OpCode:

    def __init__(self, nargs):
        self.nargs = nargs
        self.ops = []
        self.local_vars = list(range(nargs))

    def add_local_var(self):
        if self.local_vars:
            var = max(self.local_vars) + 1
        else:
            var = 0
        self.local_vars.append(var)
        return var


StrConstant = namedtuple('StrConstant', ['python_string'])
IntConstant = namedtuple('IntConstant', ['python_int'])
BoolConstant = namedtuple('BoolConstant', ['python_bool'])
CreateFunction = namedtuple('CreateFunction', [
    'name', 'body_opcode', 'is_generator'])
LookupVar = namedtuple('LookupVar', ['level', 'var'])
SetVar = namedtuple('SetVar', ['level', 'var'])
CallFunction = namedtuple('CallFunction', ['nargs', 'returns_a_value'])
PopOne = namedtuple('PopOne', [])
Return = namedtuple('Return', ['returns_a_value'])
Negation = namedtuple('Negation', [])
JumpIf = namedtuple('JumpIf', ['marker'])


# must not be a namedtuple because different JumpMarker objects must not
# compare equal
class JumpMarker:
    pass


class _OpCoder:

    def __init__(self, output_opcode: OpCode, parent_coder):
        self.output = output_opcode
        self.parent_coder = parent_coder
        if parent_coder is None:
            self.level = 0
        else:
            self.level = parent_coder.level + 1

        self.local_vars = {}    # {varname: opcode var int}

    def do_function_call(self, call):
        self.do_expression(call.function)
        for arg in call.args:
            self.do_expression(arg)
        self.output.ops.append(CallFunction(
            len(call.args), call.type is not None))

    def _get_coder_for_level(self, level):
        level_difference = self.level - level
        assert level_difference >= 0

        coder = self
        for lel in range(level_difference):
            coder = coder.parent_coder
        return coder

    def do_expression(self, expression):
        if isinstance(expression, cooked_ast.StrConstant):
            self.output.ops.append(StrConstant(expression.python_string))

        elif isinstance(expression, cooked_ast.IntConstant):
            self.output.ops.append(IntConstant(expression.python_int))

        elif isinstance(expression, cooked_ast.CallFunction):
            self.do_function_call(expression)

        elif isinstance(expression, cooked_ast.CreateFunction):
            function_opcode = OpCode(len(expression.args))
            opcoder = _OpCoder(function_opcode, self)
            for index, (argname, argtype) in enumerate(expression.args):
                opcoder.local_vars[argname] = index

            opcoder.do_body(expression.body)
            self.output.ops.append(CreateFunction(
                expression.name, function_opcode, expression.type.is_generator))

        elif isinstance(expression, cooked_ast.LookupVar):
            coder = self._get_coder_for_level(expression.level)
            self.output.ops.append(LookupVar(
                expression.level, coder.local_vars[expression.varname]))

        else:
            assert False, expression

    def do_statement(self, statement):
        if isinstance(statement, cooked_ast.CreateLocalVar):
            var = self.output.add_local_var()
            self.local_vars[statement.varname] = var
            self.do_expression(statement.initial_value)
            self.output.ops.append(SetVar(self.level, var))

        elif isinstance(statement, cooked_ast.CallFunction):
            self.do_function_call(statement)
            if statement.type is not None:
                # not a void function, ignore return value
                self.output.ops.append(PopOne())

        elif isinstance(statement, cooked_ast.SetVar):
            self.do_expression(statement.value)
            coder = self._get_coder_for_level(statement.level)
            self.output.ops.append(SetVar(
                statement.level, coder.local_vars[statement.varname]))

        elif isinstance(statement, cooked_ast.VoidReturn):
            self.output.ops.append(Return(False))

        elif isinstance(statement, cooked_ast.ValueReturn):
            self.do_expression(statement.value)
            self.output.ops.append(Return(True))

        elif isinstance(statement, cooked_ast.If):
            end_of_if_body = JumpMarker()
            end_of_else_body = JumpMarker()

            self.do_expression(statement.cond)
            self.output.ops.append(Negation())
            self.output.ops.append(JumpIf(end_of_if_body))
            for substatement in statement.if_body:
                self.do_statement(substatement)
            self.output.ops.append(BoolConstant(True))
            self.output.ops.append(JumpIf(end_of_else_body))
            self.output.ops.append(end_of_if_body)
            for substatement in statement.else_body:
                self.do_statement(substatement)
            self.output.ops.append(end_of_else_body)

        elif isinstance(statement, cooked_ast.Loop):
            beginning = JumpMarker()
            end = JumpMarker()

            if statement.init is not None:
                self.do_statement(statement.init)
            self.output.ops.append(beginning)
            self.do_expression(statement.cond)
            self.output.ops.append(Negation())
            self.output.ops.append(JumpIf(end))

            for substatement in statement.body:
                self.do_statement(substatement)
            if statement.incr is not None:
                self.do_statement(statement.incr)

            self.output.ops.append(BoolConstant(True))
            self.output.ops.append(JumpIf(beginning))
            self.output.ops.append(end)

        else:
            assert False, statement

    def _var_creating_statements(self, statement_list):
        for statement in statement_list:
            if isinstance(statement, cooked_ast.CreateLocalVar):
                yield statement
            elif isinstance(statement, cooked_ast.If):
                yield from self._var_creating_statements(statement.if_body)
                yield from self._var_creating_statements(statement.else_body)

    def do_body(self, statements):
        if iter(statements) is statements:
            # statements is an iterator, which is bad because it needs to be
            # looped over twice
            statements = list(statements)

        for statement in self._var_creating_statements(statements):
            assert statement.varname not in self.local_vars
            self.local_vars[statement.varname] = statement.varname

        for statement in statements:
            self.do_statement(statement)


def create_opcode(cooked):
    builtin_opcoder = _OpCoder(None, None)
    builtin_opcoder.local_vars.update({
        name: index
        for index, (name, type_) in enumerate(cooked_ast.BUILTINS)
    })

    output = OpCode(0)
    _OpCoder(output, builtin_opcoder).do_body(cooked)
    return output
