import collections

from . import raw_ast, common


def _astclass(name, fields):
    # type is set to None for statements
    return collections.namedtuple(name, ['location', 'type'] + fields)


StrConstant = _astclass('StrConstant', ['python_string'])
IntConstant = _astclass('IntConstant', ['python_int'])
SetVar = _astclass('SetVar', ['varname', 'level', 'value'])
LookupVar = _astclass('LookupVar', ['varname', 'level'])
LookupGenericFunction = _astclass('LookupGenericFunction',
                                  ['funcname', 'types', 'level'])
CreateFunction = _astclass('CreateFunction', ['name', 'argnames', 'body'])
CreateLocalVar = _astclass('CreateLocalVar', ['varname', 'initial_value'])
CallFunction = _astclass('CallFunction', ['function', 'args'])
VoidReturn = _astclass('VoidReturn', [])
ValueReturn = _astclass('ValueReturn', ['value'])
Yield = _astclass('Yield', ['value'])
If = _astclass('If', ['cond', 'if_body', 'else_body'])
Loop = _astclass('Loop', ['init', 'cond', 'incr', 'body'])    # while or for


# subclasses must add a name attribute
class Type:

    def undo_generics(self, type_dict):
        return self

    def __repr__(self):
        return '<cooked ast type %r>' % self.name


class BuiltinType(Type):

    def __init__(self, name):
        self.name = name


BUILTIN_TYPES = collections.OrderedDict([
    ('Str', BuiltinType('Str')),
    ('Int', BuiltinType('Int')),
    ('Bool', BuiltinType('Bool')),
])


class FunctionType(Type):

    def __init__(self, name_prefix, argtypes=(), return_or_yield_type=None,
                 is_generator=False):
        self.argtypes = list(argtypes)
        self.return_or_yield_type = return_or_yield_type
        self.is_generator = is_generator
        self.name_prefix = name_prefix
        self.name = '%s(%s)' % (
            name_prefix, ', '.join(argtype.name for argtype in argtypes))

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented
        return (self.argtypes == other.argtypes and
                self.return_or_yield_type == other.return_or_yield_type and
                self.is_generator == other.is_generator)

    def undo_generics(self, type_dict, new_name_prefix=None):
        if new_name_prefix is None:
            new_name_prefix = self.name_prefix

        return FunctionType(
            new_name_prefix,
            [tybe.undo_generics(type_dict) for tybe in self.argtypes],
            self.return_or_yield_type.undo_generics(type_dict),
            self.is_generator)


class GeneratorType(Type):

    def __init__(self, item_type):
        self.item_type = item_type
        self.name = 'Generator[%s]' % item_type.name

    def __eq__(self, other):
        if not isinstance(other, GeneratorType):
            return NotImplemented
        return self.item_type == other.item_type

    def undo_generics(self, type_dict):
        return GeneratorType(self.item_type.undo_generics(type_dict))


BUILTIN_OBJECTS = collections.OrderedDict([
    ('print', FunctionType('print', [BUILTIN_TYPES['Str']])),
    ('TRUE', BUILTIN_TYPES['Bool']),
    ('FALSE', BUILTIN_TYPES['Bool']),
])


class GenericMarker(Type):

    def __init__(self):
        # FIXME: better naming
        import random
        self.name = random.choice('ABCDEFGHIJKLMNOPQRSTUVWXYZ')

    def undo_generics(self, type_dict):
        return type_dict.get(self, self)


# note: generic functions are NOT objects
#       generic functions are NOT types
#       generic functions are something yet else :D
class GenericFunction:

    # type_markers contains GenericMarker objects
    # functype's name_prefix should be set properly
    def __init__(self, type_markers, functype):
        self.type_markers = type_markers
        self.functype = functype

    def get_function_type(self, the_types, error_location):
        if len(the_types) != len(self.type_markers):
            if len(self.type_markers) == 1:
                type_maybe_s = '1 type'
            else:
                type_maybe_s = '%d types' % len(self.type_markers)

            raise common.CompileError(
                "%s[...] expected %s, but got %d" % (
                    type_maybe_s, len(the_types)),
                error_location)

        type_dict = dict(zip(self.type_markers, the_types))
        new_name_prefix = '%s[%s]' % (
            self.functype.name_prefix,
            ', '.join(tybe.name for tybe in the_types))
        return self.functype.undo_generics(type_dict, new_name_prefix)


T = GenericMarker()
BUILTIN_GENERIC_FUNCS = collections.OrderedDict([
    ('next', GenericFunction(
        [T], FunctionType('next', [GeneratorType(T)], T))),
])
del T


class _Chef:

    def __init__(self, parent_chef, is_function=False, is_generator=False,
                 return_or_yield_type=None):
        # there's no can_yield, just check whether yield_type is not None
        if is_function:
            self.can_return = True
            self.return_type = None if is_generator else return_or_yield_type
            self.yield_type = return_or_yield_type if is_generator else None
            if is_generator:
                assert return_or_yield_type is not None
        else:
            assert not is_function
            assert return_or_yield_type is None
            self.can_return = False
            self.return_type = None
            self.yield_type = None

        self.parent_chef = parent_chef
        if parent_chef is None:
            self.level = 0
        else:
            self.level = parent_chef.level + 1

        # keys are strings, values are types
        self.local_vars = {}
        self.local_generic_funcs = {}

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

        if name in BUILTIN_TYPES:
            raise common.CompileError(
                "'%s' is not a valid %s name because it's a type name"
                % (name, what_is_it), location)

        return None

    def cook_function_call(self, raw_func_call: raw_ast.FuncCall):
        function = self.cook_expression(raw_func_call.function)
        if not isinstance(function.type, FunctionType):
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

        if function.type.is_generator:
            returning = GeneratorType(function.type.return_or_yield_type)
        else:
            returning = function.type.return_or_yield_type

        return CallFunction(raw_func_call.location, returning, function, args)

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
            return StrConstant(raw_expression.location, BUILTIN_TYPES['Str'],
                               raw_expression.python_string)

        if isinstance(raw_expression, raw_ast.Integer):
            return IntConstant(raw_expression.location, BUILTIN_TYPES['Int'],
                               raw_expression.python_int)

        if isinstance(raw_expression, raw_ast.FuncCall):
            call = self.cook_function_call(raw_expression)
            if call.function.type.return_or_yield_type is None:
                assert call.function.type.is_generator
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
            types = [self.cook_type(tybe, location)
                     for tybe, location in raw_expression.types]
            functype = generfunc.get_function_type(
                types, raw_expression.location)
            return LookupGenericFunction(
                raw_expression.location, functype, raw_expression.funcname,
                types, chef.level)

        raise NotImplementedError("oh no: " + str(raw_expression))

    def cook_type(self, typename, location):
        if typename not in BUILTIN_TYPES:
            raise common.CompileError(
                "unknown type '%s'" % typename, location)
        return BUILTIN_TYPES[typename]

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

        argnames = []
        argtypes = []
        for typename, typeloc, argname, argnameloc in raw.args:
            argtype = self.cook_type(typename, typeloc)
            self._check_name_not_exist(argname, 'variable', argnameloc)
            argnames.append(argname)
            argtypes.append(argtype)

        if raw.return_or_yield_type is None:
            return_or_yield_type = None
        else:
            # FIXME: the location is wrong because no better location is
            # available
            return_or_yield_type = self.cook_type(
                raw.return_or_yield_type, raw.location)

        functype = FunctionType(
            raw.funcname, argtypes, return_or_yield_type, raw.is_generator)

        # TODO: allow functions to call themselves
        subchef = _Chef(self, True, raw.is_generator, return_or_yield_type)
        subchef.local_vars.update(dict(zip(argnames, argtypes)))
        body = list(map(subchef.cook_statement, raw.body))
        self.local_vars[raw.funcname] = functype

        return CreateLocalVar(raw.location, functype, raw.funcname,
                              CreateFunction(raw.location, functype,
                                             raw.funcname, argnames, body))

    def cook_return(self, raw):
        if not self.can_return:
            raise common.CompileError("return outside function", raw.location)

        if self.return_type is None:
            if raw.value is not None:
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
            raise common.CompileError(
                "yield outside generator function", raw.location)

        value = self.cook_expression(raw.value)
        if value.type != self.yield_type:
            raise common.CompileError(
                ("should yield %s, not %s"
                 % (self.yield_type.name, value.type.name)),
                value.location)
        return Yield(raw.location, None, value)

    def cook_if(self, raw):
        cond = self.cook_expression(raw.condition)
        if cond.type != BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)

        if_body = list(map(self.cook_statement, raw.if_body))
        else_body = list(map(self.cook_statement, raw.else_body))
        return If(raw.location, None, cond, if_body, else_body)

    def cook_while(self, raw):
        cond = self.cook_expression(raw.condition)
        if cond.type != BUILTIN_TYPES['Bool']:
            raise common.CompileError(
                "expected Bool, got " + cond.type.name, cond.location)

        body = list(map(self.cook_statement, raw.body))
        return Loop(raw.location, None, None, cond, None, body)

    def cook_for(self, raw):
        init = self.cook_statement(raw.init)
        cond = self.cook_expression(raw.cond)
        if cond.type != BUILTIN_TYPES['Bool']:
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

        assert False, raw_statement


def cook(raw_ast_statements):
    builtin_chef = _Chef(None)
    builtin_chef.local_vars.update(BUILTIN_OBJECTS)
    builtin_chef.local_generic_funcs.update(BUILTIN_GENERIC_FUNCS)
    file_chef = _Chef(builtin_chef)
    return map(file_chef.cook_statement, raw_ast_statements)
