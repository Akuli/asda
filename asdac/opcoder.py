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
CreateFunction = _op_class('CreateFunction', ['functype', 'body_opcode'])
LookupVar = _op_class('LookupVar', ['level', 'var'])
# tuples have an index() method, avoid name clash with misspelling
LookupFromModule = _op_class('LookupFromModule', ['compilation', 'indeks'])
LookupAttribute = _op_class('LookupAttribute', ['type', 'indeks'])
SetVar = _op_class('SetVar', ['level', 'var'])
CallFunction = _op_class('CallFunction', ['nargs'])
CallConstructor = _op_class('CallConstructor', ['tybe', 'nargs'])
StrJoin = _op_class('StrJoin', ['how_many_parts'])
PopOne = _op_class('PopOne', [])
Return = _op_class('Return', ['returns_a_value'])
Throw = _op_class('Throw', [])
BoolNegation = _op_class('BoolNegation', [])
Jump = _op_class('Jump', ['marker'])
JumpIf = _op_class('JumpIf', ['marker'])
DidntReturnError = _op_class('DidntReturnError', [])
SetMethodsToClass = _op_class('SetMethodsToClass', ['klass',
                                                    'how_many_methods'])

Plus = _op_class('Plus', [])
Minus = _op_class('Minus', [])
PrefixMinus = _op_class('PrefixMinus', [])
Times = _op_class('Times', [])
# Divide = _op_class('Divide', [])
Equal = _op_class('Equal', [])

# items are tuples: (jumpto_marker, errortype, errorvarlevel, errorvar)
AddErrorHandler = _op_class('AddErrorHandler', ['items'])
RemoveErrorHandler = _op_class('RemoveErrorHandler', [])

PushFinallyStateOk = _op_class('PushFinallyStateOk', [])
PushFinallyStateError = _op_class('PushFinallyStateError', [])
PushFinallyStateReturn = _op_class('PushFinallyStateReturn', [
    'returns_a_value'])
PushFinallyStateJump = _op_class('PushFinallyStateJump', ['index'])
DiscardFinallyState = _op_class('DiscardFinallyState', [])
ApplyFinallyState = _op_class('ApplyFinallyState', [])


# convenience thing to add an error handler with just 1 item
def _add_simple_error_handler(lineno, jumpto_marker, errortype,
                              errorvarlevel, errorvar):
    item = (jumpto_marker, errortype, errorvarlevel, errorvar)
    return AddErrorHandler(lineno, [item])


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

        # keys are cooked_ast.Variable or cooked_ast.GenericVariable
        # values are VarMarker or ArgMarker
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
            self._lineno(call.location), len(call.args)))

    def _get_coder_for_level(self, level):
        level_difference = self.level - level
        assert level_difference >= 0

        coder = self
        for lel in range(level_difference):
            coder = coder.parent_coder
        return coder

    # calls a callback to add more stuff between anything that goes out of the
    # range between the start and end markers
    # the callback should return a list of ops
    # note that you may need to use this together with an error handler
    def add_more_ops_to_exit_points(self, start, end, callback):
        start_index = self.output.ops.index(start) + 1
        end_index = self.output.ops.index(end)
        index_range = range(start_index, end_index)

        self.output.ops[end_index:end_index] = callback(None)

        for index in reversed(index_range):
            op = self.output.ops[index]

            if isinstance(op, Return):
                del self.output.ops[index]
                self.output.ops[index:index] = callback(op)
            elif isinstance(op, Jump):
                if self.output.ops.index(op.marker) in index_range:
                    continue
                del self.output.ops[index]
                self.output.ops[index:index] = callback(op)
            elif isinstance(op, JumpIf):
                if self.output.ops.index(op.marker) in index_range:
                    continue

                # this is kind of tricky, the added ops must run only when the
                # jump actually happens
                jump_didnt_happen = JumpMarker()
                del self.output.ops[index]
                self.output.ops[index:index] = [
                    BoolNegation(None),
                    JumpIf(None, jump_didnt_happen),
                ] + callback(Jump(None, op.marker)) + [
                    jump_didnt_happen,
                ]
            else:
                continue

            # the correct end_index may change when a callback is called
            # setting the index_range variable does NOT affect the for loop
            end_index = self.output.ops.index(end)
            index_range = range(start_index, end_index)

    def do_expression(self, expression):
        if isinstance(expression, cooked_ast.StrConstant):
            self.output.ops.append(StrConstant(
                self._lineno(expression.location), expression.python_string))

        elif isinstance(expression, cooked_ast.IntConstant):
            self.output.ops.append(IntConstant(
                self._lineno(expression.location), expression.python_int))

        elif isinstance(expression, cooked_ast.CallFunction):
            self.do_function_call(expression)

        elif isinstance(expression, cooked_ast.New):
            for arg in expression.args:
                self.do_expression(arg)
            self.output.ops.append(CallConstructor(
                self._lineno(expression.location),
                expression.type, len(expression.args)))

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
            function_opcode = OpCode(len(expression.argvars))
            opcoder = self.create_subcoder(function_opcode)
            for index, var in enumerate(expression.argvars):
                opcoder.local_vars[var] = ArgMarker(index)

            opcoder.do_body(expression.body)
            if expression.type.returntype is None:
                function_opcode.ops.append(Return(None, False))
            else:
                function_opcode.ops.append(DidntReturnError(None))

            self.output.ops.append(CreateFunction(
                self._lineno(expression.location),
                expression.type, function_opcode))

        elif isinstance(expression, cooked_ast.LookupVar):
            coder = self._get_coder_for_level(expression.level)
            self.output.ops.append(LookupVar(
                self._lineno(expression.location), expression.level,
                coder.local_vars[expression.var]))

        elif isinstance(expression, cooked_ast.IfExpression):
            if_expr_begins = JumpMarker()
            done = JumpMarker()

            self.do_expression(expression.cond)
            self.output.ops.append(JumpIf(None, if_expr_begins))
            self.do_expression(expression.false_expr)
            self.output.ops.append(Jump(None, done))
            self.output.ops.append(if_expr_begins)
            self.do_expression(expression.true_expr)
            self.output.ops.append(done)

        elif isinstance(expression, cooked_ast.LookupFromModule):
            exported_names = list(expression.compilation.export_types.keys())
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

    def do_try_catch(self, statement):
        try_start = JumpMarker()
        try_end = JumpMarker()

        catch_starts = [JumpMarker() for catch in statement.catches]
        catches_end = JumpMarker()

        self.output.ops.append(AddErrorHandler(
            self._lineno(statement.location),
            [(catch_start, errorvar.type,
              self.level, self.local_vars[errorvar])
             for catch_start, (errorvar, body)
             in zip(catch_starts, statement.catches)]
        ))

        self.output.ops.append(try_start)
        for substatement in statement.try_body:
            self.do_statement(substatement)
        self.output.ops.append(try_end)

        def add_error_handler_remover(op):
            result = [RemoveErrorHandler(None)]
            if op is None:
                return result
            return result + [op]

        self.add_more_ops_to_exit_points(
            try_start, try_end, add_error_handler_remover)

        self.output.ops.append(Jump(None, catches_end))

        for catch_start, (errorvar, body) in zip(catch_starts,
                                                 statement.catches):
            self.output.ops.append(catch_start)
            for substatement in body:
                self.do_statement(substatement)
            self.output.ops.append(Jump(None, catches_end))

        self.output.ops.append(catches_end)

    # see finally.md
    def do_try_finally(self, statement):
        try_error_var = self.output.add_local_var()
        finally_error_var = self.output.add_local_var()
        try_error_handler_start = JumpMarker()
        finally_error_handler_start = JumpMarker()
        try_start = JumpMarker()
        try_end = JumpMarker()
        finally_start = JumpMarker()
        finally_end = JumpMarker()

        finally_state_pushed = JumpMarker()
        everything_done = JumpMarker()

        # add EH
        self.output.ops.append(_add_simple_error_handler(
            self._lineno(statement.location),
            try_error_handler_start, objects.BUILTIN_TYPES['Error'],
            self.level, try_error_var))

        # run try code
        self.output.ops.append(try_start)
        for substatement in statement.try_body:
            self.do_statement(substatement)
        self.output.ops.append(try_end)

        # remove EH, create and push FS
        def handle_try_exiting(op):
            result = [RemoveErrorHandler(None)]
            if op is None:
                result.append(PushFinallyStateOk(None))
            else:   # FIXME TODO
                raise NotImplementedError(repr(op))   # pragma: no cover
            result.append(Jump(None, finally_state_pushed))
            return result

        self.add_more_ops_to_exit_points(
            try_start, try_end, handle_try_exiting)

        # EH used, create and push FS
        self.output.ops.append(try_error_handler_start)
        self.output.ops.append(LookupVar(None, self.level, try_error_var))
        self.output.ops.append(PushFinallyStateError(None))
        # "fall through"
        self.output.ops.append(finally_state_pushed)

        # add another EH
        self.output.ops.append(_add_simple_error_handler(
            self._lineno(statement.location),
            finally_error_handler_start, objects.BUILTIN_TYPES['Error'],
            self.level, finally_error_var))

        # run finally code
        self.output.ops.append(finally_start)
        for substatement in statement.finally_body:
            self.do_statement(substatement)
        self.output.ops.append(finally_end)

        # remove EH and apply FS
        def handle_finally_exiting(op):
            return [
                RemoveErrorHandler(None),
                ApplyFinallyState(None),
                Jump(None, everything_done) if op is None else op,
            ]

        self.add_more_ops_to_exit_points(
            finally_start, finally_end, handle_finally_exiting)

        self.output.ops.append(Jump(None, everything_done))

        # finally EH: discard FS and rethrow error
        self.output.ops.append(finally_error_handler_start)
        self.output.ops.append(DiscardFinallyState(None))
        self.output.ops.append(LookupVar(
            None, self.level, finally_error_var))
        self.output.ops.append(Throw(None))

        self.output.ops.append(everything_done)

    def do_statement(self, statement):
        if isinstance(statement, cooked_ast.CreateLocalVar):
            var = self.output.add_local_var()
            assert statement.var not in self.local_vars
            self.local_vars[statement.var] = var

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
                coder.local_vars[statement.var]))

        elif isinstance(statement, cooked_ast.VoidReturn):
            self.output.ops.append(Return(
                self._lineno(statement.location), False))

        elif isinstance(statement, cooked_ast.ValueReturn):
            self.do_expression(statement.value)
            self.output.ops.append(Return(
                self._lineno(statement.location), True))

        elif isinstance(statement, cooked_ast.Throw):
            self.do_expression(statement.value)
            self.output.ops.append(Throw(self._lineno(statement.location)))

        elif isinstance(statement, cooked_ast.IfStatement):
            if_body_begins = JumpMarker()
            done = JumpMarker()

            # this is why goto is bad style :D it's quite hard to understand
            # even a basic if,else
            self.do_expression(statement.cond)
            self.output.ops.append(JumpIf(None, if_body_begins))
            for substatement in statement.else_body:
                self.do_statement(substatement)
            self.output.ops.append(Jump(None, done))
            self.output.ops.append(if_body_begins)
            for substatement in statement.if_body:
                self.do_statement(substatement)
            self.output.ops.append(done)

        elif isinstance(statement, cooked_ast.Loop):
            beginning = JumpMarker()
            end = JumpMarker()

            self.output.ops.append(beginning)
            if statement.pre_cond is not None:
                self.do_expression(statement.pre_cond)
                self.output.ops.append(BoolNegation(None))
                self.output.ops.append(JumpIf(None, end))

            for substatement in statement.body:
                self.do_statement(substatement)
            for substatement in statement.incr:
                self.do_statement(substatement)

            if statement.post_cond is None:
                self.output.ops.append(Jump(None, beginning))
            else:
                self.do_expression(statement.post_cond)
                self.output.ops.append(JumpIf(None, beginning))

            self.output.ops.append(end)

        elif isinstance(statement, cooked_ast.TryCatch):
            self.do_try_catch(statement)

        elif isinstance(statement, cooked_ast.TryFinally):
            self.do_try_finally(statement)

        elif isinstance(statement, cooked_ast.SetMethodsToClass):
            for method in statement.methods:
                self.do_expression(method)
            assert isinstance(statement.klass, objects.UserDefinedClass)
            self.output.ops.append(SetMethodsToClass(
                None, statement.klass, len(statement.methods)))

        else:
            assert False, type(statement)     # pragma: no cover

    def do_body(self, statements):
        for statement in statements:
            assert not isinstance(statement, list), statement
            self.do_statement(statement)


def create_opcode(compilation, cooked_statements, export_vars, source_code):
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    builtin_opcoder = _OpCoder(None, compilation, line_start_offsets)
    builtin_opcoder.local_vars.update({
        var: ArgMarker(index)
        for index, var in enumerate(itertools.chain(
            cooked_ast.BUILTIN_VARS.values(),
            cooked_ast.BUILTIN_GENERIC_VARS.values(),
        ))
    })

    # exported symbols are kinda like arguments
    output = OpCode(len(export_vars))
    file_opcoder = builtin_opcoder.create_subcoder(output)
    for arg_marker, var in zip(output.local_vars, export_vars.values()):
        file_opcoder.local_vars[var] = arg_marker

    file_opcoder.do_body(cooked_statements)
    output.fix_none_linenos()
    return output
