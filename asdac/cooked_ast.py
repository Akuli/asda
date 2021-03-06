import collections
import itertools

from . import raw_ast, common, objects


def _astclass(name, fields):
    # type is set to None for statements
    return collections.namedtuple(name, ['location', 'type'] + fields)


StrConstant = _astclass('StrConstant', ['python_string'])
StrJoin = _astclass('StrJoin', ['parts'])  # there are always >=2 parts
IntConstant = _astclass('IntConstant', ['python_int'])
GetVar = _astclass('GetVar', ['var'])
SetVar = _astclass('SetVar', ['var', 'value'])
GetAttr = _astclass('GetAttr', ['obj', 'attrname'])
SetAttr = _astclass('SetAttr', ['obj', 'attrname', 'value'])
GetFromModule = _astclass('GetFromModule', ['other_compilation', 'name'])
CreateFunction = _astclass('CreateFunction', ['argvars', 'body'])
CreateLocalVar = _astclass('CreateLocalVar', ['var'])
ExportObject = _astclass('ExportObject', ['name', 'value'])
CallFunction = _astclass('CallFunction', ['function', 'args'])
Return = _astclass('Return', ['value'])    # value can be None
Throw = _astclass('Throw', ['value'])
IfStatement = _astclass('IfStatement', ['cond', 'if_body', 'else_body'])
IfExpression = _astclass('IfExpression', ['cond', 'true_expr', 'false_expr'])
Loop = _astclass('Loop', ['pre_cond', 'post_cond', 'incr', 'body'])
# each item of catches is an (errorvar, body) pair
TryCatch = _astclass('TryCatch', ['try_body', 'catches'])
TryFinally = _astclass('TryFinally', ['try_body', 'finally_body'])
New = _astclass('New', ['args'])
# used when creating classes
SetMethodsToClass = _astclass('SetMethodsToClass', ['klass', 'methods'])

Plus = _astclass('Plus', ['lhs', 'rhs'])
Minus = _astclass('Minus', ['lhs', 'rhs'])
PrefixMinus = _astclass('PrefixMinus', ['prefixed'])
Times = _astclass('Times', ['lhs', 'rhs'])
# Divide = _astclass('Divide', ['lhs', 'rhs'])
IntEqual = _astclass('IntEqual', ['lhs', 'rhs'])
StrEqual = _astclass('StrEqual', ['lhs', 'rhs'])

# equalities are wrapped in this for '!=' operator
BoolNegation = _astclass('BoolNegation', ['value'])


# this is a somewhat evil function
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


# FIXME: this is wrong? collections.ChainMap.__iter__ source code is:
#
#    def __iter__(self):
#        return iter(set().union(*self.maps))

def _create_chainmap(fallback_chainmap):
    return collections.ChainMap(
        collections.OrderedDict(), *fallback_chainmap.maps)


# note that there is code that uses copy.copy() with Variable objects
class Variable:

    def __init__(self, name, tybe, definition_location, level):
        self.name = name
        self.type = tybe
        self.definition_location = definition_location    # can be None
        self.level = level

    def __repr__(self):
        return '<%s %r: level=%d>' % (
            type(self).__name__, self.name, self.level)


class GenericVariable(Variable):

    def __init__(self, generic_markers, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.generic_markers = generic_markers

    def __repr__(self):
        return "<%s '%s[%s]': level=%d>" % (
            type(self).__name__,
            self.name,
            ', '.join(marker.name for marker in self.generic_markers),
            self.level)


BUILTIN_VARS = collections.OrderedDict([
    (name, Variable(name, tybe, None, 0))
    for name, tybe in objects.BUILTIN_VARS.items()
])

BUILTIN_GENERIC_VARS = collections.OrderedDict([
    (name, GenericVariable(generic_types, name, tybe, None, 0))
    for name, (tybe, generic_types) in objects.BUILTIN_GENERIC_VARS.items()
])


class _Chef:

    def __init__(self, parent_chef, export_types,
                 is_function=False, returntype=None):
        if is_function:
            self.is_function = True
            self.returntype = returntype
        else:
            assert returntype is None
            self.is_function = False
            self.returntype = None

        self.parent_chef = parent_chef
        if parent_chef is None:
            self.level = 0
            self.import_compilations = None
            self.import_name_mapping = None

            # these are ChainMaps to make any_chef.vars.maps[0] always work
            self.vars = collections.ChainMap(BUILTIN_VARS)
            self.types = collections.ChainMap(objects.BUILTIN_TYPES)
            self.generic_vars = collections.ChainMap(BUILTIN_GENERIC_VARS)
            self.generic_types = collections.ChainMap(
                objects.BUILTIN_GENERIC_TYPES)
        else:
            # the level can be incremented immediately after creating a Chef
            self.level = parent_chef.level

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

        # keys are strings, values are type objects
        self.export_types = export_types

    def _create_subchef(self):
        return _Chef(self, self.export_types,
                     self.is_function, self.returntype)

    # there are multiple different kind of names:
    #   * types
    #   * generic types (FIXME: doesn't seem to check for those?)
    #   * variables
    #   * generic variables
    #
    # all can come from any scope
    # TODO: display definition location in error message
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

    def _get_arguments_message(self, types):
        if len(types) >= 2:
            return "arguments of types (%s)" % ', '.join(t.name for t in types)
        if len(types) == 1:
            return "one argument of type %s" % types[0].name
        assert not types
        return "no arguments"

    def _cook_arguments(self, raw_args, expected_types,
                        cannot_do_something, error_location):
        args = [self.cook_expression(arg) for arg in raw_args]
        actual_types = [arg.type for arg in args]
        if actual_types != expected_types:
            raise common.CompileError(
                "%s with %s, because %s %s needed" % (
                    cannot_do_something,
                    self._get_arguments_message(actual_types),
                    self._get_arguments_message(expected_types),
                    'is' if len(expected_types) == 1 else 'are',
                ), error_location)

        return args

    def cook_function_call(self, raw_func_call: raw_ast.FuncCall):
        function = self.cook_expression(raw_func_call.function)
        if not isinstance(function.type, objects.FunctionType):
            raise common.CompileError(
                "expected a function, got %s" % function.type.name,
                function.location)

        args = self._cook_arguments(
            raw_func_call.args, function.type.argtypes,
            "cannot call " + function.type.name, raw_func_call.location)
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

        if varname == 'this':
            raise common.CompileError(
                "'this' can be used only inside methods", error_location)

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
                tybe = obj.type.attributes[raw_expression.attrname].tybe
            except KeyError:
                raise common.CompileError(
                    "%s objects have no '%s' attribute" % (
                        obj.type.name, raw_expression.attrname),
                    raw_expression.location)

            return GetAttr(raw_expression.location, tybe,
                           obj, raw_expression.attrname)

        if isinstance(raw_expression, raw_ast.FuncCall):
            call = self.cook_function_call(raw_expression)
            if call.function.type.returntype is None:
                raise common.CompileError(
                    ("functions of type %s don't return a value"
                     % call.function.type.name),
                    raw_expression.location)
            return call

        if isinstance(raw_expression, raw_ast.New):
            tybe = self.cook_type(raw_expression.tybe)
            if tybe.constructor_argtypes is None:
                raise common.CompileError(
                    ("cannot create {0} objects with 'new {0}(...)'"
                     .format(tybe.name)),
                    raw_expression.location)

            args = self._cook_arguments(
                raw_expression.args, tybe.constructor_argtypes,
                "cannot do 'new %s(...)'" % tybe.name, raw_expression.location)
            return New(raw_expression.location, tybe, args)

        if isinstance(raw_expression, raw_ast.FuncDefinition):
            return self.cook_function_definition(raw_expression)

        if isinstance(raw_expression, raw_ast.GetVar):
            if raw_expression.module_path is None:
                chef = self.get_chef_for_varname(
                    raw_expression.varname,
                    (raw_expression.generics is not None),
                    raw_expression.location)

                if raw_expression.generics is None:
                    var = chef.vars[raw_expression.varname]
                    tybe = var.type
                else:
                    name = raw_expression.varname
                    var = chef.generic_vars[name]
                    tybe = objects.substitute_generics(
                        var.type, var.generic_markers,
                        list(map(self.cook_type, raw_expression.generics)),
                        raw_expression.location)

                return GetVar(raw_expression.location, tybe, var)

            assert raw_expression.generics is None, (
                "sorry, import and generics don't work together yet")
            compilation = self.import_compilations[raw_expression.module_path]

            try:
                tybe = compilation.export_types[raw_expression.varname]
            except KeyError:
                raise common.CompileError(
                    "\"%s\" doesn't export anything called '%s'",
                    common.path_string(raw_expression.module_path),
                    raw_expression.varname)

            return GetFromModule(
                raw_expression.location, tybe,
                compilation, raw_expression.varname)

        # from now on, 'this' is a variable
        # it is actually a keyword to prevent doing confusing things
        if isinstance(raw_expression, raw_ast.ThisExpression):
            chef = self.get_chef_for_varname(
                'this', False, raw_expression.location)
            return GetVar(raw_expression.location, chef.vars['this'].type,
                          chef.vars['this'])

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

            if raw_expression.operator == '!=':
                fake_operator = '=='
            else:
                fake_operator = raw_expression.operator

            # TODO: add == for at least Bool
            try:
                b = objects.BUILTIN_TYPES       # pep8 line length
                klass, tybe = {
                    (b['Int'], '+', b['Int']): (Plus, b['Int']),
                    (b['Int'], '-', b['Int']): (Minus, b['Int']),
                    (b['Int'], '*', b['Int']): (Times, b['Int']),
                    (b['Int'], '==', b['Int']): (IntEqual, b['Bool']),
                    (b['Str'], '==', b['Str']): (StrEqual, b['Bool']),
                }[(lhs.type, fake_operator, rhs.type)]
            except KeyError:
                raise common.CompileError(
                    "wrong types: %s %s %s" % (
                        lhs.type.name, raw_expression.operator, rhs.type.name),
                    lhs.location + rhs.location)

            result = klass(raw_expression.location, tybe, lhs, rhs)
            if raw_expression.operator == '!=':
                result = BoolNegation(
                    raw_expression.location, objects.BUILTIN_TYPES['Bool'],
                    result)
            return result

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
                    return objects.substitute_generics(
                        self.generic_types[tybe.name],
                        self.generic_types[tybe.name].generic_types,
                        list(map(self.cook_type, tybe.generics)),
                        tybe.location)
                it_is = "generic type"

            raise common.CompileError(
                "unknown %s '%s'" % (it_is, tybe.name), tybe.location)

        if isinstance(tybe, raw_ast.FuncType):
            argtypes, returntype = tybe.header
            cooked_argtypes = list(map(self.cook_type, argtypes))
            if returntype is None:
                cooked_returntype = None
            else:
                cooked_returntype = self.cook_type(returntype)

            return objects.FunctionType(cooked_argtypes, cooked_returntype)

        assert False, tybe   # pragma: no cover

    # dest = value
    def _check_assign_type(self, dest_string, dest_type, value,
                           assign_location):
        if dest_type != value.type:
            raise common.CompileError(
                "%s is of type %s, can't assign %s to it"
                % (dest_string, dest_type.name, value.type.name),
                assign_location)

    def cook_setvar(self, raw):
        value = self.cook_expression(raw.value)
        varname = raw.varname
        chef = self

        # TODO: should this use get_chef_for_varname?
        while True:
            if varname in chef.vars.maps[0]:
                if chef.level == 0:
                    raise common.CompileError(
                        "cannot set built-in variable '%s'" % varname,
                        raw.location)

                var = chef.vars.maps[0][varname]
                assert not isinstance(var, str)
                self._check_assign_type(
                    "'%s'" % varname, var.type, value, raw.location)
                return SetVar(raw.location, None, var, value)

            if chef.parent_chef is None:
                # 'this = lel' fails in raw_ast.py
                assert varname != 'this'
                raise common.CompileError(
                    "variable not found: %s" % varname,
                    raw.location)

            chef = chef.parent_chef

    def cook_setattr(self, raw):
        obj = self.cook_expression(raw.obj)
        try:
            attr = obj.type.attributes[raw.attrname]
        except KeyError:
            raise common.CompileError(
                "%s objects have no '%s' attribute" % (
                    obj.type.name, raw.attrname),
                raw.location)
        if not attr.settable:
            raise common.CompileError(
                "the '%s' attribute is not settable" % raw.attrname,
                raw.location)

        value = self.cook_expression(raw.value)
        self._check_assign_type(
            "%s.%s" % (obj.type.name, raw.attrname), attr.tybe,
            value, raw.location)
        return SetAttr(raw.location, None, obj, raw.attrname, value)

    def _check_can_export(self, location):
        # 0 = global chef, 1 = file chef, 2 = function chef, etc
        if self.level != 1:
            assert self.level >= 2
            raise common.CompileError(
                "export cannot be used in a function", location)

    # returns a list, unlike most other cook_blah methods
    def cook_let(self, raw):
        self._check_name_not_exist(raw.varname, raw.location)
        if raw.generics is None:
            value_chef = self
        else:
            # TODO: figure out whether this should use self._create_subchef
            value_chef = _Chef(self, self.export_types)
            generic_markers = collections.OrderedDict(
                (name, objects.GenericMarker(name))
                for name, location in raw.generics
            )
            value_chef.types.update(generic_markers)

        target_chef = self.parent_chef if raw.outer else self
        assert target_chef is not None

        value = value_chef.cook_expression(raw.value)

        if raw.generics is None:
            var = Variable(raw.varname, value.type, raw.location, self.level)
            target_chef.vars[raw.varname] = var
            result = [
                CreateLocalVar(raw.location, None, var),
                SetVar(raw.location, None, var, value),
            ]

            if raw.export:
                target_chef._check_can_export(raw.location)
                target_chef.export_types[raw.varname] = var.type
                result.append(ExportObject(
                    raw.location, None,
                    var.name, GetVar(raw.location, var.type, var)))

            return result

        assert not raw.export, "sorry, cannot export generic variables yet :("

        var = GenericVariable(
            list(generic_markers.values()), raw.varname, value.type,
            raw.location, self.level)
        target_chef.generic_vars[raw.varname] = var
        return [
            CreateLocalVar(raw.location, None, var),
            SetVar(raw.location, None, var,
                   _replace_generic_markers_with_object(
                        value, list(generic_markers.values()))),
        ]

    # TODO: allow functions to call themselves
    def cook_function_definition(self, raw, *, this_type=None):
        argnames = []
        argtypes = []
        argvars = []
        raw_args, raw_returntype = raw.header

        if this_type is not None:
            argnames.append('this')
            argtypes.append(this_type)
            argvars.append(Variable(
                'this', this_type, raw.location, self.level + 1))

        for raw_argtype, argname, argnameloc in raw_args:
            argtype = self.cook_type(raw_argtype)
            self._check_name_not_exist(argname, argnameloc)
            argnames.append(argname)
            argtypes.append(argtype)
            argvars.append(Variable(
                argname, argtype, argnameloc, self.level + 1))

        if raw_returntype is None:
            returntype = None
        else:
            returntype = self.cook_type(raw_returntype)

        subchef = _Chef(self, self.export_types, True, returntype)
        subchef.level += 1
        subchef.vars.update(dict(zip(argnames, argvars)))
        functype = objects.FunctionType(argtypes, returntype)
        body = subchef.cook_body(raw.body, new_subchef=False)

        return CreateFunction(raw.location, functype, argvars, body)

    def cook_return(self, raw):
        if not self.is_function:
            raise common.CompileError("return outside function", raw.location)

        if self.returntype is None:
            if raw.value is not None:
                raise common.CompileError(
                    "cannot return a value from a void function",
                    raw.value.location)
            return Return(raw.location, None, None)
        if raw.value is None:
            raise common.CompileError("missing return value", raw.location)

        value = self.cook_expression(raw.value)
        if value.type != self.returntype:
            raise common.CompileError(
                ("should return %s, not %s"
                 % (self.returntype.name, value.type.name)),
                value.location)
        return Return(raw.location, None, value)

    def cook_throw(self, raw):
        value = self.cook_expression(raw.value)

        # TODO: rewrite 'isinstance' into a separate thing
        parent_types = []
        tybe = value.type
        while tybe is not None:
            assert len(parent_types) < 12345    # safety to prevent insanities
            parent_types.append(tybe)
            tybe = tybe.parent_type
        is_error = objects.BUILTIN_TYPES['Error'] in parent_types

        if not is_error:
            raise common.CompileError(
                "should be an Error object", raw.value.location)
        return Throw(raw.location, None, value)

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
    # TODO: use functools.reduce?
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
            else_body = [self.cook_if_statement(raw._replace(ifs=raw.ifs[1:]))]

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
        subchef = self._create_subchef()
        init = subchef.cook_statement(raw.init)
        cond = subchef.cook_expression(raw.cond)
        if cond.type != objects.BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)

        incr = subchef.cook_statement(raw.incr)
        body = subchef.cook_body(raw.body, new_subchef=False)
        return init + [Loop(raw.location, None, cond, None, incr, body)]

    def cook_try_catch(self, try_location, raw_try_body, raw_catches):
        cooked_try_body = self.cook_body(raw_try_body)
        if not raw_catches:
            return cooked_try_body

        create_local_vars = []
        catches = []

        for (catch_location, errortype, varname, varname_location,
             catch_body) in raw_catches:
            self._check_name_not_exist(varname, varname_location)
            cooked_errortype = self.cook_type(errortype)

            catch_chef = self._create_subchef()
            errorvar = Variable(varname, cooked_errortype, varname_location,
                                self.level)
            catch_chef.vars[varname] = errorvar
            cooked_catch_body = catch_chef.cook_body(
                catch_body, new_subchef=False)

            create_local_vars.append(CreateLocalVar(
                varname_location, None, errorvar))
            catches.append((errorvar, cooked_catch_body))

        return (create_local_vars +
                [TryCatch(try_location, None, cooked_try_body, catches)])

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
    #            A
    #        catch Error1 e1:
    #            B
    #        catch Error2 e2:
    #            C
    #    finally:
    #        D
    #
    # but NOT this:
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
    #
    # because C must not run when B raises Error2
    def cook_try(self, raw_try):
        cooked_try_catch = self.cook_try_catch(
            raw_try.location, raw_try.try_body, raw_try.catches)

        if raw_try.finally_body:
            return self.cook_try_finally(
                cooked_try_catch,
                raw_try.finally_location, raw_try.finally_body)
        return cooked_try_catch

    def cook_class(self, raw_class):
        cooked_types = collections.OrderedDict(
            (name, self.cook_type(tybe))
            for tybe, name, location in raw_class.args)
        tybe = objects.UserDefinedClass(raw_class.name, cooked_types)
        self.types[raw_class.name] = tybe

        methods = []
        for name, name_location, funcdef in raw_class.methods:
            cooked_funcdef = self.cook_function_definition(
                funcdef, this_type=tybe)
            methods.append(cooked_funcdef)
            assert name not in tybe.attributes   # checked by raw_ast
            tybe.attributes[name] = objects.Attribute(
                cooked_funcdef.type.remove_this_arg(tybe), False)

        return SetMethodsToClass(raw_class.location, None, tybe, methods)

    # returns a list, unlike most other cook_blah methods
    def cook_statement(self, raw_statement):
        if isinstance(raw_statement, raw_ast.Let):
            return self.cook_let(raw_statement)
        if isinstance(raw_statement, raw_ast.SetVar):
            return [self.cook_setvar(raw_statement)]
        if isinstance(raw_statement, raw_ast.SetAttr):
            return [self.cook_setattr(raw_statement)]
        if isinstance(raw_statement, raw_ast.FuncCall):
            return [self.cook_function_call(raw_statement)]
        if isinstance(raw_statement, raw_ast.Return):
            return [self.cook_return(raw_statement)]
        if isinstance(raw_statement, raw_ast.Throw):
            return [self.cook_throw(raw_statement)]
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
        if isinstance(raw_statement, raw_ast.Class):
            return [self.cook_class(raw_statement)]

        assert False, raw_statement     # pragma: no cover

    def cook_body(self, raw_statements, *, new_subchef=True):
        if new_subchef:
            return self._create_subchef().cook_body(
                raw_statements, new_subchef=False)

        flatten = itertools.chain.from_iterable
        return list(flatten(map(self.cook_statement, raw_statements)))


def cook(compilation, raw_ast_statements, import_compilation_dict):
    builtin_chef = _Chef(None, None)     # TODO: is this needed?

    export_types = collections.OrderedDict()
    file_chef = _Chef(builtin_chef, export_types)
    file_chef.level += 1
    file_chef.import_compilations = import_compilation_dict
    cooked_statements = file_chef.cook_body(
        raw_ast_statements, new_subchef=False)

    return (cooked_statements, export_types)
