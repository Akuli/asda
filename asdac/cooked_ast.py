import collections
import itertools

from . import raw_ast, common, objects


def _astclass(name, fields):
    # type is set to None for statements
    return collections.namedtuple(name, ['location', 'type'] + fields)


StrConstant = _astclass('StrConstant', ['python_string'])
StrJoin = _astclass('StrJoin', ['parts'])  # there are always >=2 parts
IntConstant = _astclass('IntConstant', ['python_int'])
SetVar = _astclass('SetVar', ['varname', 'level', 'value'])
LookupVar = _astclass('LookupVar', ['varname', 'level'])
LookupFromModule = _astclass('LookupFromModule', ['compilation', 'name'])
LookupAttr = _astclass('LookupAttr', ['obj', 'attrname'])
LookupGenericFunction = _astclass('LookupGenericFunction',
                                  ['funcname', 'types', 'level'])
LookupModule = _astclass('LookupModule', [])
CreateFunction = _astclass('CreateFunction', ['argnames', 'body', 'yields'])
CreateLocalVar = _astclass('CreateLocalVar', ['varname'])
CallFunction = _astclass('CallFunction', ['function', 'args'])
VoidReturn = _astclass('VoidReturn', [])
ValueReturn = _astclass('ValueReturn', ['value'])
Yield = _astclass('Yield', ['value'])
IfStatement = _astclass('IfStatement', ['cond', 'if_body', 'else_body'])
IfExpression = _astclass('IfExpression', ['cond', 'true_expr', 'false_expr'])
Loop = _astclass('Loop', ['pre_cond', 'post_cond', 'incr', 'body'])
TryCatch = _astclass('TryCatch', ['try_body', 'errortype', 'caught_varname',
                                  'catch_body'])
TryFinally = _astclass('TryFinally', ['try_body', 'finally_body'])

Plus = _astclass('Plus', ['lhs', 'rhs'])
Minus = _astclass('Minus', ['lhs', 'rhs'])
PrefixMinus = _astclass('PrefixMinus', ['prefixed'])
Times = _astclass('Times', ['lhs', 'rhs'])
# Divide = _astclass('Divide', ['lhs', 'rhs'])
Equal = _astclass('Equal', ['lhs', 'rhs'])
NotEqual = _astclass('NotEqual', ['lhs', 'rhs'])


# this is a somewhat evil function
def _find_yields(node):
    if isinstance(node, list):
        for sub in node:
            yield from _find_yields(sub)
    elif isinstance(node, raw_ast.Yield):
        yield node.location
    # namedtuples are tuples >:D MUHAHAHAAAA!!
    elif (isinstance(node, tuple) and
          not isinstance(node, raw_ast.FuncDefinition)):
        yield from _find_yields(list(node))


# this is too
def _replace_generic_markers_with_object(node, markers):
    node = node._replace(type=node.type.undo_generics(
        dict.fromkeys(markers, objects.BUILTIN_TYPES['Object'])))

    for name, value in node._asdict().items():
        if name in ['location', 'type']:
            continue

        # FIXME: what if the value is a list
        if not (isinstance(value, tuple) and
                hasattr(value, 'location') and
                hasattr(value, 'type')):
            # it is not a cooked ast namedtuple
            continue

        node = node._replace(**{
            name: _replace_generic_markers_with_object(value, markers)
        })

    return node


def _create_chainmap(fallback_chainmap):
    return collections.ChainMap(
        collections.OrderedDict(), *fallback_chainmap.maps)


class _Chef:

    def __init__(self, parent_chef, is_function=False, yields=False,
                 returntype=None):
        # there's no self.can_yield, just check whether yield_type is not None
        if is_function:
            self.can_return = True
            if yields:
                assert isinstance(returntype, objects.GeneratorType)
                self.yield_type = returntype.item_type
                self.return_type = None
            else:
                self.yield_type = None
                self.return_type = returntype
        else:
            assert returntype is None
            assert not yields
            self.can_return = False
            self.yield_type = None
            self.return_type = None

        self.parent_chef = parent_chef
        if parent_chef is None:
            self.level = 0
            self.import_compilations = None
            self.import_name_mapping = None

            # these are ChainMaps to make any_chef.vars.maps[0] always work
            self.vars = collections.ChainMap(objects.BUILTIN_VARS)
            self.types = collections.ChainMap(objects.BUILTIN_TYPES)
            self.generic_vars = collections.ChainMap(
                objects.BUILTIN_GENERIC_VARS)
            self.generic_types = collections.ChainMap(
                objects.BUILTIN_GENERIC_TYPES)
        else:
            self.level = parent_chef.level + 1

            # keys are paths, values are Compilation objects
            self.import_compilations = parent_chef.import_compilations

            # keys are names from import statements, values are paths
            if parent_chef.import_name_mapping is None:
                self.import_name_mapping = {}
            else:
                self.import_name_mapping = parent_chef.import_name_mapping

            self.vars = _create_chainmap(parent_chef.vars)
            self.types = _create_chainmap(parent_chef.types)
            self.generic_vars = _create_chainmap(parent_chef.generic_vars)
            self.generic_types = _create_chainmap(parent_chef.generic_types)

        # keys are strings, values are types
        # TODO: why are export vars "local"? what does it mean?
        self.local_export_vars = collections.OrderedDict()

    # there are multiple different kind of names:
    #   * types
    #   * generic types (TODO)
    #   * variables
    #   * generic variables
    #
    # all can come from any scope
    def _check_name_not_exist(self, name, location):
        if name in self.types:
            raise common.CompileError(
                "there's already a '%s' type" % name, location)
        if name in self.vars:
            raise common.CompileError(
                "there's already a '%s' variable" % name, location)
        if name in self.generic_vars:
            raise common.CompileError(
                "there's already a generic '%s' variable" % name, location)

    def cook_function_call(self, raw_func_call: raw_ast.FuncCall):
        function = self.cook_expression(raw_func_call.function)
        if not isinstance(function.type, objects.FunctionType):
            raise common.CompileError(
                "expected a function, got %s" % function.type.name,
                function.location)

        args = [self.cook_expression(arg) for arg in raw_func_call.args]
        if [arg.type for arg in args] != function.type.argtypes:
            if len(args) >= 2:
                message_end = "arguments of types (%s)" % ', '.join(
                    arg.type.name for arg in args)
            elif len(args) == 1:
                message_end = "an argument of type %s" % args[0].type.name
            elif not args:
                message_end = "no arguments"
            else:
                raise RuntimeError("wuut")
            raise common.CompileError(
                "cannot call %s with %s" % (function.type.name, message_end),
                raw_func_call.location)

        return CallFunction(raw_func_call.location, function.type.returntype,
                            function, args)

    def get_chef_for_varname(self, varname, is_generic, error_location):
        chef = self
        while chef is not None:
            if is_generic:
                if varname in chef.generic_vars.maps[0]:
                    return chef
            else:
                if varname in chef.vars.maps[0]:
                    return chef
            chef = chef.parent_chef

        message = "variable not found: " + varname
        if is_generic:
            message = "generic " + message
        raise common.CompileError(message, error_location)

    def cook_expression(self, raw_expression):
        if isinstance(raw_expression, raw_ast.String):
            return StrConstant(raw_expression.location,
                               objects.BUILTIN_TYPES['Str'],
                               raw_expression.python_string)

        if isinstance(raw_expression, raw_ast.Integer):
            return IntConstant(raw_expression.location,
                               objects.BUILTIN_TYPES['Int'],
                               raw_expression.python_int)

        if isinstance(raw_expression, raw_ast.GetAttr):
            obj = self.cook_expression(raw_expression.obj)
            try:
                tybe = obj.type.attributes[raw_expression.attrname]
            except KeyError as e:
                raise common.CompileError(
                    "%s objects have no '%s' attribute" % (
                        obj.type.name, raw_expression.attrname),
                    raw_expression.location)

            return LookupAttr(raw_expression.location, tybe,
                              obj, raw_expression.attrname)

        if isinstance(raw_expression, raw_ast.FuncCall):
            call = self.cook_function_call(raw_expression)
            if call.function.type.returntype is None:
                raise common.CompileError(
                    "%s doesn't return a value" % call.function.type.name,
                    raw_expression.location)
            return call

        if isinstance(raw_expression, raw_ast.FuncDefinition):
            return self.cook_function_definition(raw_expression)

        if isinstance(raw_expression, raw_ast.GetVar):
            if raw_expression.module_path is None:
                chef = self.get_chef_for_varname(
                    raw_expression.varname,
                    (raw_expression.generics is not None),
                    raw_expression.location)

                if raw_expression.generics is None:
                    tybe = chef.vars[raw_expression.varname]
                else:
                    name = raw_expression.varname   # pep8 line length
                    tybe = chef.generic_vars[name].get_real_type(
                        list(map(self.cook_type, raw_expression.generics)),
                        raw_expression.location)

                return LookupVar(
                    raw_expression.location, tybe,
                    raw_expression.varname, chef.level)

            assert raw_expression.generics is None, (
                "sorry, import and generics don't work together yet")
            compilation = self.import_compilations[raw_expression.module_path]

            try:
                tybe = compilation.exports[raw_expression.varname]
            except KeyError:
                raise common.CompileError(
                    "\"%s\" doesn't export anything called '%s'",
                    common.path_string(raw_expression.module_path),
                    raw_expression.varname)

            return LookupFromModule(
                raw_expression.location, tybe,
                compilation, raw_expression.varname)

        if isinstance(raw_expression, raw_ast.StrJoin):
            return StrJoin(
                raw_expression.location, objects.BUILTIN_TYPES['Str'],
                list(map(self.cook_expression, raw_expression.parts)))

        if isinstance(raw_expression, raw_ast.PrefixOperator):
            assert raw_expression.operator == '-'
            integer = self.cook_expression(raw_expression.expression)
            if integer.type is not objects.BUILTIN_TYPES['Int']:
                raise common.CompileError(
                    "expected -Int, got -%s" % integer.type.name,
                    raw_expression.location)
            return PrefixMinus(
                raw_expression.location, objects.BUILTIN_TYPES['Int'], integer)

        # TODO: make this much less hard-coded
        if isinstance(raw_expression, raw_ast.BinaryOperator):
            lhs = self.cook_expression(raw_expression.lhs)
            rhs = self.cook_expression(raw_expression.rhs)

            if raw_expression.operator == '/':
                # i want 3/2 to return 1.5 as a float or fraction object, but
                # the only number type i have now is Int
                raise common.CompileError(
                    "sorry, division is not supported yet :(",
                    raw_expression.location)

            # TODO: add == for at least Str and Bool
            if lhs.type is not objects.BUILTIN_TYPES['Int']:
                problem = lhs.location
            elif rhs.type is not objects.BUILTIN_TYPES['Int']:
                problem = rhs.location
            else:
                problem = None

            if problem is not None:
                raise common.CompileError(
                    "expected Int %s Int, got %s %s %s"
                    % (raw_expression.operator, lhs.type.name,
                       raw_expression.operator, rhs.type.name),
                    problem)

            klass, tybe = {
                '+': (Plus, objects.BUILTIN_TYPES['Int']),
                '-': (Minus, objects.BUILTIN_TYPES['Int']),
                '*': (Times, objects.BUILTIN_TYPES['Int']),
                '==': (Equal, objects.BUILTIN_TYPES['Bool']),
                '!=': (NotEqual, objects.BUILTIN_TYPES['Bool']),
            }[raw_expression.operator]
            return klass(raw_expression.location, tybe, lhs, rhs)

        if isinstance(raw_expression, raw_ast.IfExpression):
            cond = self.cook_expression(raw_expression.cond)
            if cond.type != objects.BUILTIN_TYPES['Bool']:
                raise common.CompileError(
                    "expected Bool, got " + cond.type.name, cond.location)
            true_expr = self.cook_expression(raw_expression.true_expr)
            false_expr = self.cook_expression(raw_expression.false_expr)
            if true_expr.type != false_expr.type:
                raise common.CompileError(
                    "'then' value has type %s, but 'else' value has type %s"
                    % (true_expr.type.name, false_expr.type.name),
                    raw_expression.location)
            return IfExpression(raw_expression.location, true_expr.type,
                                cond, true_expr, false_expr)

        raise NotImplementedError(      # pragma: no cover
            "oh no: " + str(type(raw_expression)))

    def cook_type(self, tybe):
        if isinstance(tybe, raw_ast.GetType):
            if tybe.generics is None:
                if tybe.name in self.types:
                    return self.types[tybe.name]
                it_is = "type"
            else:
                if tybe.name in self.generic_types:
                    return self.generic_types[tybe.name].get_real_type(
                        list(map(self.cook_type, tybe.generics)),
                        tybe.location)
                it_is = "generic type"

            raise common.CompileError(
                "unknown %s '%s'" % (it_is, tybe.name), tybe.location)

        # TODO: support generic types again
#        if isinstance(tybe, raw_ast.FromGeneric):   # generic type
#            if tybe.name not in objects.BUILTIN_GENERIC_TYPES:
#                raise common.CompileError(
#                    "unknown generic type '%s'" % tybe.name,
#                    tybe.location)
#
#            genertype = objects.BUILTIN_GENERIC_TYPES[tybe.name]
#            types = list(map(self.cook_type, tybe.types))
#            result = genertype.get_real_type(types, tybe.location)
#            return result

        assert False, tybe   # pragma: no cover

    def cook_setvar(self, raw):
        cooked_value = self.cook_expression(raw.value)
        varname = raw.varname
        chef = self

        while True:
            if varname in chef.vars.maps[0]:
                if cooked_value.type != chef.vars.maps[0][varname]:
                    raise common.CompileError(
                        ("'%s' is of type %s, can't assign %s to it"
                         % (varname, chef.vars[varname].name,
                            cooked_value.type.name)),
                        raw.location)
                return SetVar(
                    raw.location, None,
                    varname, chef.level, cooked_value)

            if chef.parent_chef is None:
                raise common.CompileError(
                    "variable not found: %s" % varname,
                    raw.location)

            chef = chef.parent_chef

    # returns a list, unlike most other cook_blah methods
    def cook_let(self, raw):
        self._check_name_not_exist(raw.varname, raw.location)
        if raw.generics is None:
            chef = self
        else:
            chef = _Chef(self)

            # the level is used in later steps only, but before those steps,
            # this file actually replaces all generics types with Object, so
            # that this...
            #
            #   let do_nothing[T] = (T value) -> T:
            #       return value
            #
            # ...produces the same cooked ast as this:
            #
            #   let do_nothing = (Object value) -> Object:
            #       return value
            #
            # this needs 1 more chef in the top code than in the bottom code,
            # but that must not be visible outside this file
            chef.level -= 1

            generic_markers = collections.OrderedDict(
                (name, objects.GenericMarker(name))
                for name, location in raw.generics
            )
            chef.types.update(generic_markers)

        value = chef.cook_expression(raw.value)

        if raw.generics is None:
            if raw.export:
                self._check_can_export(raw.location)
                self.local_export_vars[raw.varname] = value.type
                return [SetVar(raw.location, None, raw.varname,
                               self.level, value)]

            self.vars[raw.varname] = value.type
            return [
                CreateLocalVar(raw.location, None, raw.varname),
                SetVar(raw.location, None, raw.varname, self.level, value),
            ]

        assert not raw.export, "sorry, cannot export generic variables yet :("

        generic = objects.Generic(
            list(generic_markers.values()), value.type)
        self.generic_vars[raw.varname] = generic
        return [
            CreateLocalVar(raw.location, None, raw.varname),
            SetVar(raw.location, None, raw.varname, self.level,
                   _replace_generic_markers_with_object(
                        value, list(generic_markers.values()))),
        ]

    # TODO: allow functions to call themselves
    def cook_function_definition(self, raw):
        argnames = []
        argtypes = []
        for raw_argtype, argname, argnameloc in raw.args:
            argtype = self.cook_type(raw_argtype)
            self._check_name_not_exist(argname, argnameloc)
            argnames.append(argname)
            argtypes.append(argtype)

        if raw.returntype is None:
            returntype = None
        else:
            returntype = self.cook_type(raw.returntype)

        yield_location = next(_find_yields(raw.body), None)
        if (yield_location is not None and
                not isinstance(returntype, objects.GeneratorType)):
            raise common.CompileError(
                "cannot yield in a function that doesn't return "
                "Generator[something]", yield_location)

        subchef = _Chef(self, True, yield_location is not None, returntype)
        subchef.vars.update(dict(zip(argnames, argtypes)))
        functype = objects.FunctionType(argtypes, returntype)
        body = subchef.cook_body(raw.body)

        return CreateFunction(raw.location, functype,
                              argnames, body, yield_location is not None)

    def cook_return(self, raw):
        if not self.can_return:
            raise common.CompileError("return outside function", raw.location)

        if self.return_type is None:
            if raw.value is not None:
                if self.yield_type is None:
                    raise common.CompileError(
                        "cannot return a value from a void function",
                        raw.value.location)
                raise common.CompileError(
                    "cannot return a value from a function that yields",
                    raw.location)
            return VoidReturn(raw.location, None)
        if raw.value is None:
            raise common.CompileError("missing return value", raw.location)

        value = self.cook_expression(raw.value)
        if value.type != self.return_type:
            raise common.CompileError(
                ("should return %s, not %s"
                 % (self.return_type.name, value.type.name)),
                value.location)
        return ValueReturn(raw.location, None, value)

    def cook_yield(self, raw):
        if self.yield_type is None:
            # the only way how we can get here is that this is not a function
            # see cook_function_definition()
            raise common.CompileError("yield outside function", raw.location)

        value = self.cook_expression(raw.value)
        if value.type != self.yield_type:
            raise common.CompileError(
                ("should yield %s, not %s"
                 % (self.yield_type.name, value.type.name)),
                value.location)
        return Yield(raw.location, None, value)

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
    #       else:
    #           if cond3:
    #               body3
    #           else:
    #               body4
    #
    # TODO: use functools.reduce
    def cook_if_statement(self, raw):
        raw_cond, raw_if_body = raw.ifs[0]
        cond = self.cook_expression(raw_cond)
        if cond.type != objects.BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)
        if_body = self.cook_body(raw_if_body)

        if len(raw.ifs) == 1:
            else_body = self.cook_body(raw.else_body)
        else:
            # _replace is a documented namedtuple method, it has _ in front to
            # allow creating a namedtuple with an attribute named 'replace'
            else_body = [self.cook_if(raw._replace(ifs=raw.ifs[1:]))]

        return IfStatement(cond.location, None, cond, if_body, else_body)

    def cook_while(self, raw):
        cond = self.cook_expression(raw.cond)
        if cond.type != objects.BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)

        body = self.cook_body(raw.body)
        return Loop(raw.location, None, cond, None, [], body)

    def cook_do_while(self, raw):
        body = self.cook_body(raw.body)
        cond = self.cook_expression(raw.cond)
        if cond.type != objects.BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)
        return Loop(raw.location, None, None, cond, [], body)

    # returns a list, unlike most other things
    def cook_for(self, raw):
        init = self.cook_statement(raw.init)
        cond = self.cook_expression(raw.cond)
        if cond.type != objects.BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)
        incr = self.cook_statement(raw.incr)
        body = self.cook_body(raw.body)
        return init + [Loop(raw.location, None, cond, None, incr, body)]

    def cook_try_catch(self, cooked_try_body, catch_location, errortype,
                       varname, varname_location, catch_body):
        self._check_name_not_exist(varname, varname_location)
        cooked_errortype = self.cook_type(errortype)
        self.vars[varname] = cooked_errortype
        cooked_catch_body = self.cook_body(catch_body)

        return [
            CreateLocalVar(varname_location, None, varname),
            TryCatch(catch_location, None, cooked_try_body, cooked_errortype,
                     varname, cooked_catch_body),
        ]

    def cook_try_finally(self, cooked_try_body, finally_location,
                         finally_body):
        cooked_finally_body = self.cook_body(finally_body)
        return [
            TryFinally(finally_location, None,
                       cooked_try_body, cooked_finally_body),
        ]

    # turns this:
    #
    #    try:
    #        A
    #    catch Error1 e1:
    #        B
    #    catch Error2 e2:
    #        C
    #    finally:
    #        D
    #
    # into this:
    #
    #    try:
    #        try:
    #            try:
    #                A
    #            catch Error1 e1:
    #                B
    #        catch Error2 e2:
    #            C
    #    finally:
    #        D
    def cook_try(self, raw_try):
        if raw_try.finally_body:
            if raw_try.catches:
                cooked_try_body = self.cook_try(
                    raw_try._replace(finally_body=[]))
            else:
                cooked_try_body = self.cook_body(raw_try.try_body)

            return self.cook_try_finally(
                cooked_try_body,
                raw_try.finally_location, raw_try.finally_body)

        if raw_try.catches:
            assert raw_try.catches
            less_catches_cooked = self.cook_try(
                raw_try._replace(catches=raw_try.catches[:-1]))
            return self.cook_try_catch(
                less_catches_cooked, *raw_try.catches[-1])

        return self.cook_body(raw_try.try_body)

    def _check_can_export(self, location):
        # 0 = global chef, 1 = file chef, 2 = function chef, etc
        if self.level != 1:
            assert self.level >= 2
            raise common.CompileError(
                "export cannot be used in a function", location)

    # returns a list, unlike most other cook_blah methods
    def cook_statement(self, raw_statement):
        if isinstance(raw_statement, raw_ast.Let):
            return self.cook_let(raw_statement)
        if isinstance(raw_statement, raw_ast.SetVar):
            return [self.cook_setvar(raw_statement)]
        if isinstance(raw_statement, raw_ast.FuncCall):
            return [self.cook_function_call(raw_statement)]
        if isinstance(raw_statement, raw_ast.Return):
            return [self.cook_return(raw_statement)]
        if isinstance(raw_statement, raw_ast.Yield):
            return [self.cook_yield(raw_statement)]
        if isinstance(raw_statement, raw_ast.VoidStatement):
            return []
        if isinstance(raw_statement, raw_ast.IfStatement):
            return [self.cook_if_statement(raw_statement)]
        if isinstance(raw_statement, raw_ast.While):
            return [self.cook_while(raw_statement)]
        if isinstance(raw_statement, raw_ast.DoWhile):
            return [self.cook_do_while(raw_statement)]
        if isinstance(raw_statement, raw_ast.For):
            return self.cook_for(raw_statement)
        if isinstance(raw_statement, raw_ast.Try):
            return self.cook_try(raw_statement)

        assert False, raw_statement     # pragma: no cover

    def cook_body(self, raw_statements):
        flatten = itertools.chain.from_iterable
        return list(flatten(map(self.cook_statement, raw_statements)))


def cook(compilation, raw_ast_statements, import_compilation_dict):
    builtin_chef = _Chef(None)

    file_chef = _Chef(builtin_chef)
    file_chef.import_compilations = import_compilation_dict
    cooked_statements = file_chef.cook_body(raw_ast_statements)
    return (cooked_statements, file_chef.local_export_vars)
