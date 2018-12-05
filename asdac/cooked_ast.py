import collections

from . import raw_ast, common


def _astclass(name, fields):
    # type is set to None for statements
    return collections.namedtuple(name, ['location', 'type'] + fields)


StrConstant = _astclass('StrConstant', ['python_string'])
IntConstant = _astclass('IntConstant', ['python_int'])
SetVar = _astclass('SetVar', ['varname', 'level', 'value'])
LookupVar = _astclass('LookupVar', ['varname', 'level'])
CreateFunction = _astclass('CreateFunction', ['name', 'args', 'body'])
CreateLocalVar = _astclass('CreateLocalVar', ['varname', 'initial_value'])
CallFunction = _astclass('CallFunction', ['function', 'args'])
VoidReturn = _astclass('VoidReturn', [])
ValueReturn = _astclass('ValueReturn', ['value'])
Yield = _astclass('Yield', ['value'])
If = _astclass('If', ['cond', 'if_body', 'else_body'])
Loop = _astclass('Loop', ['init', 'cond', 'incr', 'body'])    # while or for


# subclasses must add a name attribute
class Type:

    def __repr__(self):
        return '<cooked ast type %r>' % self.name


class BuiltinType(Type):

    def __init__(self, name):
        self.name = name


TYPES = {
    'Str': BuiltinType('Str'),
    'Int': BuiltinType('Int'),
    'Bool': BuiltinType('Bool'),
}


class FunctionType(Type):

    def __init__(self, name, argtypes=(), return_or_yield_type=None,
                 is_generator=False):
        self.argtypes = list(argtypes)
        self.return_or_yield_type = return_or_yield_type
        self.is_generator = is_generator

        self.name = '%s(%s)' % (
            name, ', '.join(argtype.name for argtype in argtypes))

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented
        return (self.argtypes == other.argtypes and
                self.return_or_yield_type == other.return_or_yield_type and
                self.is_generator == other.is_generator)


class GeneratorType(Type):

    def __init__(self, item_type):
        self.item_type = item_type
        self.name = 'Generator[%s]' % item_type.name

    def __eq__(self, other):
        if not isinstance(other, GeneratorType):
            return NotImplemented
        return self.item_type == other.item_type


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

        self.local_vars = {}    # keys are strings, values are types

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

    def get_chef_for_varname(self, varname):
        chef = self
        while True:
            if varname in chef.local_vars:
                return chef
            if chef.parent_chef is None:
                return None
            chef = chef.parent_chef

    def cook_expression(self, raw_expression):
        if isinstance(raw_expression, raw_ast.String):
            return StrConstant(raw_expression.location, TYPES['Str'],
                               raw_expression.python_string)

        if isinstance(raw_expression, raw_ast.Integer):
            return IntConstant(raw_expression.location, TYPES['Int'],
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
            chef = self.get_chef_for_varname(raw_expression.varname)
            if chef is None:
                raise common.CompileError(
                   "variable not found: %s" % raw_expression.varname,
                   raw_expression.location)
            return LookupVar(
                raw_expression.location,
                chef.local_vars[raw_expression.varname],
                raw_expression.varname, chef.level)

        raise NotImplementedError("oh no: " + str(raw_expression))

    def cook_type(self, typename, location):
        if typename not in TYPES:
            raise common.CompileError(
                "unknown type '%s'" % typename, location)
        return TYPES[typename]

    def cook_statement(self, raw_statement):
        if isinstance(raw_statement, raw_ast.Let):
            # TODO: error if the variable is defined in an outer scope, or not?
            if raw_statement.varname in self.local_vars:
                raise common.CompileError(
                    ("there's already a variable named '%s'"
                     % raw_statement.varname), raw_statement.location)

            value = self.cook_expression(raw_statement.value)
            self.local_vars[raw_statement.varname] = value.type
            return CreateLocalVar(raw_statement.location, None,
                                  raw_statement.varname, value)

        if isinstance(raw_statement, raw_ast.SetVar):
            cooked_value = self.cook_expression(raw_statement.value)
            varname = raw_statement.varname
            chef = self

            while True:
                if varname in chef.local_vars:
                    if cooked_value.type != chef.local_vars[varname]:
                        raise common.CompileError(
                            ("'%s' is of type %s, can't assign %s to it"
                             % (varname, chef.local_vars[varname].name,
                                cooked_value.type.name)),
                            raw_statement.location)
                    return SetVar(
                        raw_statement.location, None,
                        varname, chef.level, cooked_value)
                if chef.parent_chef is None:
                    raise common.CompileError(
                        "variable not found: %s" % varname,
                        raw_statement.location)

                chef = chef.parent_chef

        if isinstance(raw_statement, raw_ast.FuncCall):
            return self.cook_function_call(raw_statement)

        if isinstance(raw_statement, raw_ast.FuncDefinition):
            if self.get_chef_for_varname(raw_statement.funcname) is not None:
                raise common.CompileError(
                    ("there's already a variable named '%s'"
                     % raw_statement.funcname), raw_statement.location)

            args = []
            for typename, typeloc, argname, argnameloc in raw_statement.args:
                type_ = self.cook_type(typename, typeloc)
                if self.get_chef_for_varname(argname) is not None:
                    raise common.CompileError(
                        "there's already a variable named '%s'" % argname,
                        argnameloc)

                args.append((argname, type_))

            if raw_statement.return_or_yield_type is None:
                return_or_yield_type = None
            else:
                # FIXME: the location is wrong because no better location is
                # available
                return_or_yield_type = self.cook_type(
                    raw_statement.return_or_yield_type, raw_statement.location)

            functype = FunctionType(
                raw_statement.funcname, [arg[1] for arg in args],
                return_or_yield_type, raw_statement.is_generator)

            # TODO: allow functions to call themselves
            subchef = _Chef(self, True, raw_statement.is_generator,
                            return_or_yield_type)
            subchef.local_vars.update(dict(args))
            body = list(map(subchef.cook_statement, raw_statement.body))
            self.local_vars[raw_statement.funcname] = functype

            return CreateLocalVar(
                raw_statement.location, functype, raw_statement.funcname,
                CreateFunction(raw_statement.location, functype,
                               raw_statement.funcname, args, body))

        if isinstance(raw_statement, raw_ast.Return):
            if not self.can_return:
                raise common.CompileError(
                    "return outside function", raw_statement.location)

            if self.return_type is None:
                if raw_statement.value is not None:
                    raise common.CompileError(
                        "cannot return a value from a void function",
                        raw_statement.value.location)
                return VoidReturn(raw_statement.location, None)
            else:
                if raw_statement.value is None:
                    raise common.CompileError(
                        "missing return value", raw_statement.location)
                value = self.cook_expression(raw_statement.value)
                if value.type != self.return_type:
                    raise common.CompileError(
                        ("should return %s, not %s"
                         % (self.return_type.name, value.type.name)),
                        value.location)
                return ValueReturn(raw_statement.location, None, value)

        if isinstance(raw_statement, raw_ast.Yield):
            if self.yield_type is None:
                raise common.CompileError(
                    "yield outside generator function", raw_statement.location)

            value = self.cook_expression(raw_statement.value)
            if value.type != self.yield_type:
                raise common.CompileError(
                    ("should yield %s, not %s"
                     % (self.yield_type.name, value.type.name)),
                    value.location)
            return Yield(raw_statement.location, None, value)

        if isinstance(raw_statement, raw_ast.If):
            cond = self.cook_expression(raw_statement.condition)
            if cond.type != TYPES['Bool']:
                raise common.CompileError(
                    "expected Bool, got " + cond.type.name, cond.location)

            if_body = list(map(self.cook_statement, raw_statement.if_body))
            else_body = list(map(self.cook_statement, raw_statement.else_body))
            return If(raw_statement.location, None, cond, if_body, else_body)

        if isinstance(raw_statement, raw_ast.While):
            cond = self.cook_expression(raw_statement.condition)
            if cond.type != TYPES['Bool']:
                raise common.CompileError(
                    "expected Bool, got " + cond.type.name, cond.location)

            body = list(map(self.cook_statement, raw_statement.body))
            return Loop(raw_statement.location, None, None, cond, None, body)

        if isinstance(raw_statement, raw_ast.For):
            init = self.cook_statement(raw_statement.init)
            cond = self.cook_expression(raw_statement.cond)
            if cond.type != TYPES['Bool']:
                raise common.CompileError(
                    "expected Bool, got " + cond.type.name, cond.location)
            incr = self.cook_statement(raw_statement.incr)
            body = list(map(self.cook_statement, raw_statement.body))
            return Loop(raw_statement.location, None, init, cond, incr, body)

        assert False, raw_statement


BUILTINS = [
    ('print', FunctionType('print', [TYPES['Str']])),
    ('TRUE', TYPES['Bool']),
    ('FALSE', TYPES['Bool']),
    # FIXME: next shouldn't be just for string generators, needs generics
    ('next', FunctionType('next', [GeneratorType(TYPES['Str'])],
                          TYPES['Str'])),
]


def cook(raw_ast_statements):
    builtin_chef = _Chef(None)
    builtin_chef.local_vars.update(dict(BUILTINS))
    file_chef = _Chef(builtin_chef)
    return map(file_chef.cook_statement, raw_ast_statements)
