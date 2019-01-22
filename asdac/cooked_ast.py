import collections

from . import raw_ast, common, objects


def _astclass(name, fields):
    # type is set to None for statements
    return collections.namedtuple(name, ['location', 'type'] + fields)


StrConstant = _astclass('StrConstant', ['python_string'])
IntConstant = _astclass('IntConstant', ['python_int'])
SetVar = _astclass('SetVar', ['varname', 'level', 'value'])
LookupVar = _astclass('LookupVar', ['varname', 'level'])
LookupAttr = _astclass('LookupAttr', ['obj', 'attrname'])
LookupGenericFunction = _astclass('LookupGenericFunction',
                                  ['funcname', 'types', 'level'])
CreateFunction = _astclass('CreateFunction',
                           ['name', 'argnames', 'body', 'yields'])
CreateGenericFunction = _astclass('CreateGenericFunction',
                                  ['name', 'generic_obj', 'argnames', 'body',
                                   'yields'])
CreateLocalVar = _astclass('CreateLocalVar', ['varname', 'initial_value'])
CallFunction = _astclass('CallFunction', ['function', 'args'])
VoidReturn = _astclass('VoidReturn', [])
ValueReturn = _astclass('ValueReturn', ['value'])
Yield = _astclass('Yield', ['value'])
If = _astclass('If', ['ifs', 'else_body'])
Loop = _astclass('Loop', ['init', 'cond', 'incr', 'body'])    # while or for


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
            self.can_return = False
            self.yield_type = None
            self.return_type = None

        self.parent_chef = parent_chef
        if parent_chef is None:
            self.level = 0
        else:
            self.level = parent_chef.level + 1

        # keys are strings, values are types
        self.local_vars = {}
        self.local_generic_funcs = {}
        self.local_types = {}

    # there are multiple different kind of names:
    #   * types (currently all types are built-in)
    #   * variables (from several different scopes)
    def _check_name_not_exist(self, name, what_is_it, location):
        chef = self
        while chef is not None:
            if name in chef.local_vars:
                raise common.CompileError(
                    "there's already a '%s' variable" % name,
                    location)
            if name in chef.local_generic_funcs:
                raise common.CompileError(
                    "there's already a generic '%s' function" % name,
                    location)
            chef = chef.parent_chef

        if name in objects.BUILTIN_TYPES:
            raise common.CompileError(
                "'%s' is not a valid %s name because it's a type name"
                % (name, what_is_it), location)

        return None

    def cook_function_call(self, raw_func_call: raw_ast.FuncCall):
        function = self.cook_expression(raw_func_call.function)
        if not isinstance(function.type, objects.FunctionType):
            raise common.CompileError(
                "expected a function, got %s" % function.type.name,
                function.location)

        args = [self.cook_expression(arg) for arg in raw_func_call.args]
        if [arg.type for arg in args] != function.type.argtypes:
            if args:
                message_end = "arguments of types: " + ', '.join(
                    arg.type.name for arg in args)
            else:
                message_end = "no arguments"
            raise common.CompileError(
                "cannot call %s with %s" % (function.type.name, message_end),
                raw_func_call.location)

        return CallFunction(raw_func_call.location, function.type.returntype,
                            function, args)

    # get_chef_for_blah()s are kinda copy/pasta but not tooo bad imo
    def get_chef_for_varname(self, varname, error_location):
        chef = self
        while chef is not None:
            if varname in chef.local_vars:
                return chef
            chef = chef.parent_chef

        raise common.CompileError(
            "variable not found: %s" % varname, error_location)

    def get_chef_for_generic_func_name(self, generfuncname, error_location):
        chef = self
        while chef is not None:
            if generfuncname in chef.local_generic_funcs:
                return chef
            chef = chef.parent_chef

        raise common.CompileError(
            "generic function not found: %s" % generfuncname, error_location)

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
            # currently all attributes are method names
            obj = self.cook_expression(raw_expression.obj)
            try:
                tybe = obj.type.methods[raw_expression.attrname]
            except KeyError as e:
                raise common.CompileError(
                    # remember to replace 'method' with 'attribute' when other
                    # attributes exist!
                    "%s objects have no '%s' method" % (
                        obj.type.name, raw_expression.attrname),
                    raw_expression.location)

            return LookupAttr(raw_expression.location, tybe.without_this_arg(),
                              obj, raw_expression.attrname)

        if isinstance(raw_expression, raw_ast.FuncCall):
            call = self.cook_function_call(raw_expression)
            if call.function.type.returntype is None:
                raise common.CompileError(
                    "%s doesn't return a value" % call.function.type.name,
                    raw_expression.location)
            return call

        if isinstance(raw_expression, raw_ast.GetVar):
            chef = self.get_chef_for_varname(
                raw_expression.varname, raw_expression.location)
            return LookupVar(
                raw_expression.location,
                chef.local_vars[raw_expression.varname],
                raw_expression.varname, chef.level)

        if isinstance(raw_expression, raw_ast.FuncFromGeneric):
            chef = self.get_chef_for_generic_func_name(
                raw_expression.funcname, raw_expression.location)
            generfunc = chef.local_generic_funcs[raw_expression.funcname]
            types = list(map(self.cook_type, raw_expression.types))
            functype = generfunc.get_real_type(types, raw_expression.location)
            return LookupGenericFunction(
                raw_expression.location, functype, raw_expression.funcname,
                types, chef.level)

        raise NotImplementedError(      # pragma: no cover
            "oh no: " + str(raw_expression))

    def cook_type(self, tybe):
        if isinstance(tybe, raw_ast.GetType):
            if tybe.name in objects.BUILTIN_TYPES:
                return objects.BUILTIN_TYPES[tybe.name]
            if tybe.name in self.local_types:
                return self.local_types[tybe.name]
            raise common.CompileError(
                "unknown type '%s'" % tybe.name, tybe.location)

        if isinstance(tybe, raw_ast.TypeFromGeneric):
            if tybe.typename not in objects.BUILTIN_GENERIC_TYPES:
                raise common.CompileError(
                    "unknown generic type '%s'" % tybe.typename,
                    tybe.location)

            genertype = objects.BUILTIN_GENERIC_TYPES[tybe.typename]
            types = list(map(self.cook_type, tybe.types))
            result = genertype.get_real_type(types, tybe.location)
            return result

        assert False, tybe   # pragma: no cover

    def cook_let(self, raw):
        self._check_name_not_exist(raw.varname, 'variable', raw.location)
        value = self.cook_expression(raw.value)
        self.local_vars[raw.varname] = value.type
        return CreateLocalVar(raw.location, None, raw.varname, value)

    def cook_setvar(self, raw):
        cooked_value = self.cook_expression(raw.value)
        varname = raw.varname
        chef = self

        while True:
            if varname in chef.local_vars:
                if cooked_value.type != chef.local_vars[varname]:
                    raise common.CompileError(
                        ("'%s' is of type %s, can't assign %s to it"
                         % (varname, chef.local_vars[varname].name,
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

    def cook_function_definition(self, raw):
        self._check_name_not_exist(raw.funcname, 'variable', raw.location)

        # yes, this is weird
        # why this is needed is explained below
        temp_chef = _Chef(self)

        if raw.generics is not None:
            markers = []
            for name, location in raw.generics:
                self._check_name_not_exist(name, 'generic type', location)
                marker = objects.GenericMarker(name)
                temp_chef.local_types[name] = marker
                markers.append(marker)

        argnames = []
        argtypes = []
        for raw_argtype, argname, argnameloc in raw.args:
            argtype = temp_chef.cook_type(raw_argtype)
            temp_chef._check_name_not_exist(argname, 'variable', argnameloc)
            argnames.append(argname)
            argtypes.append(argtype)

        if raw.returntype is None:
            returntype = None
        else:
            returntype = temp_chef.cook_type(raw.returntype)

        # here you can see why temp_chef is needed:
        # * creating the real subchef needs cooked returntype
        # * cooking the returntype needs a chef that knows the generic types
        yield_location = next(_find_yields(raw.body), None)
        subchef = _Chef(self, True, yield_location is not None, returntype)
        subchef.local_types.update(temp_chef.local_types)
        if (yield_location is not None and
                not isinstance(returntype, objects.GeneratorType)):
            raise common.CompileError(
                "cannot yield in a function that doesn't return "
                "Generator[something]", yield_location)

        functype = objects.FunctionType(raw.funcname, argtypes, returntype)

        # TODO: allow functions to call themselves
        subchef.local_vars.update(dict(zip(argnames, argtypes)))
        body = list(map(subchef.cook_statement, raw.body))

        if raw.generics is None:
            self.local_vars[raw.funcname] = functype
            return CreateLocalVar(raw.location, None, raw.funcname,
                                  CreateFunction(raw.location, functype,
                                                 raw.funcname, argnames, body,
                                                 yield_location is not None))

        generic_obj = objects.Generic(markers, functype)
        self.local_generic_funcs[raw.funcname] = generic_obj
        return CreateGenericFunction(
            raw.location, None, raw.funcname, generic_obj, argnames, body,
            yield_location is not None)

    def cook_return(self, raw):
        if not self.can_return:
            raise common.CompileError("return outside function", raw.location)

        if self.return_type is None:
            if raw.value is not None:
                if self.yield_type is not None:
                    raise common.CompileError(
                        "cannot return a value from a function that yields",
                        raw.location)
                raise common.CompileError(
                    "cannot return a value from a void function",
                    raw.value.location)
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
            raise common.CompileError("yield outside function", raw.location)

        value = self.cook_expression(raw.value)
        if value.type != self.yield_type:
            raise common.CompileError(
                ("should yield %s, not %s"
                 % (self.yield_type.name, value.type.name)),
                value.location)
        return Yield(raw.location, None, value)

    def cook_if(self, raw):
        cooked_ifs = []
        for cond, body in raw.ifs:
            cooked_cond = self.cook_expression(cond)
            if cooked_cond.type != objects.BUILTIN_TYPES['Bool']:
                raise common.CompileError(
                    "expected Bool, got " + cooked_cond.type.name,
                    cooked_cond.location)

            cooked_ifs.append((cooked_cond,
                               list(map(self.cook_statement, body))))

        cooked_else_body = list(map(self.cook_statement, raw.else_body))
        return If(raw.location, None, cooked_ifs, cooked_else_body)

    def cook_while(self, raw):
        cond = self.cook_expression(raw.condition)
        if cond.type != objects.BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)

        body = list(map(self.cook_statement, raw.body))
        return Loop(raw.location, None, None, cond, None, body)

    def cook_for(self, raw):
        init = self.cook_statement(raw.init)
        cond = self.cook_expression(raw.cond)
        if cond.type != objects.BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)
        incr = self.cook_statement(raw.incr)
        body = list(map(self.cook_statement, raw.body))
        return Loop(raw.location, None, init, cond, incr, body)

    def cook_statement(self, raw_statement):
        if isinstance(raw_statement, raw_ast.Let):
            return self.cook_let(raw_statement)
        if isinstance(raw_statement, raw_ast.SetVar):
            return self.cook_setvar(raw_statement)
        if isinstance(raw_statement, raw_ast.FuncCall):
            return self.cook_function_call(raw_statement)
        if isinstance(raw_statement, raw_ast.FuncDefinition):
            return self.cook_function_definition(raw_statement)
        if isinstance(raw_statement, raw_ast.Return):
            return self.cook_return(raw_statement)
        if isinstance(raw_statement, raw_ast.Yield):
            return self.cook_yield(raw_statement)
        if isinstance(raw_statement, raw_ast.If):
            return self.cook_if(raw_statement)
        if isinstance(raw_statement, raw_ast.While):
            return self.cook_while(raw_statement)
        if isinstance(raw_statement, raw_ast.For):
            return self.cook_for(raw_statement)

        assert False, raw_statement     # pragma: no cover


def cook(raw_ast_statements):
    builtin_chef = _Chef(None)
    builtin_chef.local_vars.update(objects.BUILTIN_OBJECTS)
    builtin_chef.local_generic_funcs.update(objects.BUILTIN_GENERIC_FUNCS)
    file_chef = _Chef(builtin_chef)
    return map(file_chef.cook_statement, raw_ast_statements)
