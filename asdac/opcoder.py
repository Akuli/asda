import bisect
import collections
import io
import itertools

from . import common, cooked_ast, objects


class VarMarker(common.Marker):
    pass


class ArgMarker:

    def __init__(self, index):
        self.index = index

    def __repr__(self):
        return '%s(%d)' % (type(self).__name__, self.index)


# lineno is None for ops that don't correspond to a cooked ast node
def _op_class(name, fields):
    return collections.namedtuple(name, ['lineno'] + fields)


# all types are cooked_ast types
StrConstant = _op_class('StrConstant', ['python_string'])
IntConstant = _op_class('IntConstant', ['python_int'])
BoolConstant = _op_class('BoolConstant', ['python_bool'])
CreateFunction = _op_class('CreateFunction', [
    'functype', 'yields', 'body_opcode'])
LookupVar = _op_class('LookupVar', ['level', 'var'])
# tuples have an index() method, avoid name clash with misspelling
LookupFromModule = _op_class('LookupFromModule', ['compilation', 'indeks'])
LookupAttribute = _op_class('LookupAttribute', ['type', 'indeks'])
SetVar = _op_class('SetVar', ['level', 'var'])
CallFunction = _op_class('CallFunction', ['nargs', 'returns_a_value'])
StrJoin = _op_class('StrJoin', ['how_many_parts'])
PopOne = _op_class('PopOne', [])
Return = _op_class('Return', ['returns_a_value'])
Yield = _op_class('Yield', [])
BoolNegation = _op_class('BoolNegation', [])
JumpIf = _op_class('JumpIf', ['marker'])
DidntReturnError = _op_class('DidntReturnError', [])

Plus = _op_class('Plus', [])
Minus = _op_class('Minus', [])
PrefixMinus = _op_class('PrefixMinus', [])
Times = _op_class('Times', [])
# Divide = _op_class('Divide', [])
Equal = _op_class('Equal', [])


class JumpMarker(common.Marker):

    def __init__(self):
        super().__init__()
        self.lineno = None


# debugging tip: pprint.pprint(opcode.ops)
class OpCode:

    def __init__(self, nargs):
        self.nargs = nargs
        self.ops = []
        self.local_vars = [ArgMarker(i) for i in range(nargs)]

    def add_local_var(self):
        var = VarMarker()
        self.local_vars.append(var)
        return var

    def _get_all_ops(self):
        # i wish python had pointer objects or something :(
        # sucks to yield (list, index) pairs
        # in c, i could use &self.ops[index]
        for index, op in enumerate(self.ops):
            yield (self.ops, index)
            if isinstance(op, CreateFunction):
                yield from op.body_opcode._get_all_ops()

    def fix_none_linenos(self):
        current_lineno = 1
        for lizt, index in self._get_all_ops():
            if lizt[index].lineno is None:
                if isinstance(lizt[index], JumpMarker):
                    lizt[index].lineno = current_lineno
                else:
                    # _replace is a documented namedtuple method, it has _ to
                    # allow creating a namedtuple with a 'replace' attribute
                    lizt[index] = lizt[index]._replace(lineno=current_lineno)
            else:
                current_lineno = lizt[index].lineno


class _OpCoder:

    def __init__(self, output_opcode, compilation, line_start_offsets):
        self.output = output_opcode
        self.parent_coder = None
        self.level = 0
        self.compilation = compilation
        self.line_start_offsets = line_start_offsets

        # {varname: VarMarker or ArgMarker}
        self.local_vars = {}

    def create_subcoder(self, output_opcode):
        result = _OpCoder(output_opcode, self.compilation,
                          self.line_start_offsets)
        result.parent_coder = self
        result.level = self.level + 1
        return result

    # returns line number so that 1 means first line
    def _lineno(self, location):
        #    >>> offsets = [0, 4, 10]
        #    >>> bisect.bisect(offsets, 0)
        #    1
        #    >>> bisect.bisect(offsets, 3)
        #    1
        #    >>> bisect.bisect(offsets, 4)
        #    2
        #    >>> bisect.bisect(offsets, 8)
        #    2
        #    >>> bisect.bisect(offsets, 9)
        #    2
        #    >>> bisect.bisect(offsets, 10)
        #    3
        assert location.compilation == self.compilation
        return bisect.bisect(self.line_start_offsets, location.offset)

    def do_function_call(self, call):
        self.do_expression(call.function)
        for arg in call.args:
            self.do_expression(arg)
        self.output.ops.append(CallFunction(
            self._lineno(call.location), len(call.args),
            call.type is not None))

    def _get_coder_for_level(self, level):
        level_difference = self.level - level
        assert level_difference >= 0

        coder = self
        for lel in range(level_difference):
            coder = coder.parent_coder
        return coder

    def do_expression(self, expression):
        if isinstance(expression, cooked_ast.StrConstant):
            self.output.ops.append(StrConstant(
                self._lineno(expression.location), expression.python_string))

        elif isinstance(expression, cooked_ast.IntConstant):
            self.output.ops.append(IntConstant(
                self._lineno(expression.location), expression.python_int))

        elif isinstance(expression, cooked_ast.CallFunction):
            self.do_function_call(expression)

        elif isinstance(expression, cooked_ast.StrJoin):
            for part in expression.parts:
                self.do_expression(part)
            self.output.ops.append(StrJoin(
                self._lineno(expression.location), len(expression.parts)))

        # the whole functype is in the opcode because even though the opcode is
        # not statically typed, each object has a type
        #
        # in things like BoolConstant the interpreter knows that the type will
        # be Bool, but there are many different function types because
        # functions with different argument types or return type have
        # different types
        #
        # general rule: if something creates a new object, make sure to include
        # enough information for the interpreter to tell what the type of the
        # object should be
        elif isinstance(expression, cooked_ast.CreateFunction):
            function_opcode = OpCode(len(expression.argnames))
            opcoder = self.create_subcoder(function_opcode)
            for index, argname in enumerate(expression.argnames):
                opcoder.local_vars[argname] = ArgMarker(index)

            opcoder.do_body(expression.body)
            if expression.type.returntype is None or expression.yields:
                function_opcode.ops.append(Return(None, False))
            else:
                function_opcode.ops.append(DidntReturnError(None))

            self.output.ops.append(CreateFunction(
                self._lineno(expression.location),
                expression.type, expression.yields, function_opcode))

        elif isinstance(expression, cooked_ast.LookupVar):
            coder = self._get_coder_for_level(expression.level)
            if isinstance(expression, cooked_ast.LookupVar):
                name = expression.varname
            else:
                name = expression.funcname
            self.output.ops.append(LookupVar(
                self._lineno(expression.location), expression.level,
                coder.local_vars[name]))

        elif isinstance(expression, cooked_ast.LookupFromModule):
            exported_names = list(expression.compilation.exports.keys())
            self.output.ops.append(LookupFromModule(
                self._lineno(expression.location),
                expression.compilation,
                exported_names.index(expression.name)))

        elif isinstance(expression, cooked_ast.LookupAttr):
            self.do_expression(expression.obj)
            attribute_names = list(expression.obj.type.attributes.keys())
            index = attribute_names.index(expression.attrname)
            self.output.ops.append(LookupAttribute(
                self._lineno(expression.location), expression.obj.type, index))

        elif isinstance(expression, cooked_ast.PrefixMinus):
            self.do_expression(expression.prefixed)
            self.output.ops.append(PrefixMinus(
                self._lineno(expression.location)))

        else:
            binary_operators = [
                (cooked_ast.Plus, Plus),
                (cooked_ast.Minus, Minus),
                (cooked_ast.Times, Times),
                # (cooked_ast.Divide, Divide),
                (cooked_ast.Equal, Equal),
                (cooked_ast.NotEqual, Equal),   # see below
            ]
            for cooked_ast_class, opcoder_class in binary_operators:
                if isinstance(expression, cooked_ast_class):
                    self.do_expression(expression.lhs)
                    self.do_expression(expression.rhs)
                    self.output.ops.append(opcoder_class(
                        self._lineno(expression.location)))
                    if isinstance(expression, cooked_ast.NotEqual):
                        self.output.ops.append(BoolNegation(None))
                    return

            assert False, expression    # pragma: no cover

    def do_statement(self, statement):
        if isinstance(statement, cooked_ast.CreateLocalVar):
            var = self.output.add_local_var()
            assert statement.varname not in self.local_vars
            self.local_vars[statement.varname] = var
            self.do_expression(statement.initial_value)
            self.output.ops.append(SetVar(
                self._lineno(statement.location), self.level, var))

        elif isinstance(statement, cooked_ast.CallFunction):
            self.do_function_call(statement)
            if statement.type is not None:
                # not a void function, ignore return value
                self.output.ops.append(PopOne(
                    self._lineno(statement.location)))

        elif isinstance(statement, cooked_ast.SetVar):
            self.do_expression(statement.value)
            coder = self._get_coder_for_level(statement.level)
            self.output.ops.append(SetVar(
                self._lineno(statement.location), statement.level,
                coder.local_vars[statement.varname]))

        elif isinstance(statement, cooked_ast.VoidReturn):
            self.output.ops.append(Return(
                self._lineno(statement.location), False))

        elif isinstance(statement, cooked_ast.ValueReturn):
            self.do_expression(statement.value)
            self.output.ops.append(Return(
                self._lineno(statement.location), True))

        elif isinstance(statement, cooked_ast.Yield):
            self.do_expression(statement.value)
            self.output.ops.append(Yield(self._lineno(statement.location)))

        elif isinstance(statement, cooked_ast.If):
            end_of_if_body = JumpMarker()
            end_of_else_body = JumpMarker()

            # this is why goto is bad style :D it's quite hard to understand
            # even a basic if,else
            self.do_expression(statement.condition)
            self.output.ops.append(BoolNegation(None))
            self.output.ops.append(JumpIf(None, end_of_if_body))
            for substatement in statement.if_body:
                self.do_statement(substatement)
            self.output.ops.append(BoolConstant(None, True))
            self.output.ops.append(JumpIf(None, end_of_else_body))
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
            self.output.ops.append(BoolNegation(None))
            self.output.ops.append(JumpIf(None, end))

            for substatement in statement.body:
                self.do_statement(substatement)
            if statement.incr is not None:
                self.do_statement(statement.incr)

            self.output.ops.append(BoolConstant(None, True))
            self.output.ops.append(JumpIf(None, beginning))
            self.output.ops.append(end)

        elif isinstance(statement, cooked_ast.CreateGenericFunction):
            dynamic_functype = statement.generic_obj.get_real_type(
                [tybe.parent_type
                 for tybe in statement.generic_obj.type_markers],
                statement.location)
            self.do_statement(cooked_ast.CreateLocalVar(
                statement.location, None, statement.name,
                cooked_ast.CreateFunction(
                    statement.location, dynamic_functype, statement.name,
                    statement.argnames, statement.body, statement.yields)))

        else:
            assert False, statement     # pragma: no cover

    def do_body(self, statements):
        for statement in statements:
            assert not isinstance(statement, list)
            self.do_statement(statement)


def create_opcode(compilation, cooked_statements, source_code):
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    builtin_opcoder = _OpCoder(None, compilation, line_start_offsets)
    builtin_opcoder.line_start_offsets.extend(line_start_offsets)
    builtin_opcoder.local_vars.update({
        name: ArgMarker(index)
        for index, name in enumerate(itertools.chain(
            objects.BUILTIN_VARS.keys(),
            objects.BUILTIN_GENERIC_VARS.keys()
        ))
    })

    # exported symbols are kinda like arguments
    output = OpCode(len(compilation.exports))
    file_opcoder = builtin_opcoder.create_subcoder(output)
    for arg_marker, name in zip(output.local_vars, compilation.exports.keys()):
        file_opcoder.local_vars[name] = arg_marker

    file_opcoder.do_body(cooked_statements)
    output.fix_none_linenos()
    return output
