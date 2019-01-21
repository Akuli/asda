from collections import namedtuple
import itertools

from . import cooked_ast, objects


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


# all types are cooked_ast types
StrConstant = namedtuple('StrConstant', ['python_string'])
IntConstant = namedtuple('IntConstant', ['python_int'])
BoolConstant = namedtuple('BoolConstant', ['python_bool'])
CreateFunction = namedtuple('CreateFunction', [
    'name', 'functype', 'yields', 'body_opcode'])
LookupVar = namedtuple('LookupVar', ['level', 'var'])
# tuples have an index() method, avoid name clash with misspelling
LookupMethod = namedtuple('LookupMethod', ['type', 'indeks'])
SetVar = namedtuple('SetVar', ['level', 'var'])
CallFunction = namedtuple('CallFunction', ['nargs', 'returns_a_value'])
PopOne = namedtuple('PopOne', [])
Return = namedtuple('Return', ['returns_a_value'])
Yield = namedtuple('Yield', [])
Negation = namedtuple('Negation', [])
JumpIf = namedtuple('JumpIf', ['marker'])


# must not be a namedtuple because different JumpMarker objects must not
# compare equal
class JumpMarker:
    # this used to be "class JumpMarker: pass" but this count thing is
    # more debuggable imo
    _counts = itertools.count(1)

    def __init__(self):
        self._count = next(type(self)._counts)

    def __repr__(self):
        return '<JumpMarker %d>' % self._count


class _OpCoder:

    def __init__(self, output_opcode: OpCode, parent_coder):
        self.output = output_opcode
        self.parent_coder = parent_coder
        if parent_coder is None:
            self.level = 0
        else:
            self.level = parent_coder.level + 1

        self.local_vars = {}    # {varname: opcode var int id}

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
            function_opcode = OpCode(len(expression.argnames))
            opcoder = _OpCoder(function_opcode, self)
            for index, argname in enumerate(expression.argnames):
                opcoder.local_vars[argname] = index

            opcoder.do_body(expression.body)
            self.output.ops.append(CreateFunction(expression.name,
                                                  expression.type,
                                                  expression.yields,
                                                  function_opcode))

        # the opcode is dynamically typed from here, so generic functions
        # are treated same as variables
        elif isinstance(expression, (cooked_ast.LookupVar,
                                     cooked_ast.LookupGenericFunction)):
            coder = self._get_coder_for_level(expression.level)
            if isinstance(expression, cooked_ast.LookupVar):
                name = expression.varname
            else:
                name = expression.funcname
            self.output.ops.append(LookupVar(
                expression.level, coder.local_vars[name]))

        elif isinstance(expression, cooked_ast.LookupAttr):
            self.do_expression(expression.obj)
            method_names = list(expression.obj.type.methods.keys())
            index = method_names.index(expression.attrname)
            self.output.ops.append(LookupMethod(expression.obj.type, index))

        else:
            assert False, expression    # pragma: no cover

    def do_statement(self, statement):
        if isinstance(statement, cooked_ast.CreateLocalVar):
            var = self.output.add_local_var()
            assert statement.varname not in self.local_vars
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

        elif isinstance(statement, cooked_ast.Yield):
            self.do_expression(statement.value)
            self.output.ops.append(Yield())

        elif isinstance(statement, cooked_ast.If):
            if len(statement.ifs) > 1:
                # this turns this...
                #
                #   if cond1:
                #       body1
                #   elif cond2:
                #       body2
                #   elif cond3:
                #       body3
                #   else:
                #       body4
                #
                # ...into this:
                #
                #   if cond1:
                #       body1
                #   else:
                #       if cond2:
                #           body2
                #       elif cond3:
                #           body3
                #       else:
                #           body4
                #
                # then recursion handles the rest of the conditions
                first_cond_body, *rest = statement.ifs
                else_of_first = cooked_ast.If(
                    statement.location, statement.type,
                    rest, statement.else_body)
                simple_if = cooked_ast.If(
                    statement.location, statement.type,
                    [first_cond_body], [else_of_first])
            else:
                simple_if = statement

            [(cond, if_body)] = simple_if.ifs
            end_of_if_body = JumpMarker()
            end_of_else_body = JumpMarker()

            self.do_expression(cond)
            self.output.ops.append(Negation())
            self.output.ops.append(JumpIf(end_of_if_body))
            for substatement in if_body:
                self.do_statement(substatement)
            self.output.ops.append(BoolConstant(True))
            self.output.ops.append(JumpIf(end_of_else_body))
            self.output.ops.append(end_of_if_body)
            for substatement in simple_if.else_body:
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
            assert False, statement     # pragma: no cover

    def do_body(self, statements):
        if iter(statements) is statements:
            # statements is an iterator, which is bad because it needs to be
            # looped over twice
            statements = list(statements)

        for statement in statements:
            self.do_statement(statement)


def create_opcode(cooked):
    builtin_opcoder = _OpCoder(None, None)
    builtin_opcoder.local_vars.update({
        name: index
        for index, name in enumerate(itertools.chain(
            objects.BUILTIN_OBJECTS.keys(),
            objects.BUILTIN_GENERIC_FUNCS.keys()
        ))
    })

    output = OpCode(0)
    _OpCoder(output, builtin_opcoder).do_body(cooked)
    return output
