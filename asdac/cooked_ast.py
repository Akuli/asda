import abc
import collections

from . import raw_ast, common


def _astclass(name, fields):
    # type is set to None for e.g. calls to void functions
    return collections.namedtuple(name, ['location', 'type'] + fields)


StrConstant = _astclass('StrConstant', ['python_string'])
IntConstant = _astclass('IntConstant', ['python_int'])
SetVar = _astclass('SetVar', ['varname', 'level', 'value'])
LookupVar = _astclass('LookupVar', ['varname', 'level'])
CreateFunction = _astclass('CreateFunction', ['name', 'body'])
CreateLocalVar = _astclass('CreateLocalVar', ['varname', 'initial_value'])
CallFunction = _astclass('CallFunction', ['function', 'args'])


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
}


class FunctionType(Type):

    def __init__(self, name, *argtypes, returntype=None):
        self.argtypes = argtypes
        self.returntype = returntype    # None for void functions

        self.name = '%s(%s)' % (
            name, ', '.join(argtype.name for argtype in argtypes))

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented
        return (self.argtypes == other.argtypes and
                self.returntype == other.returntype)


class _Chef:

    def __init__(self, parent_chef):
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
        if tuple(arg.type for arg in args) != function.type.argtypes:
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

    def cook_expression(self, raw_expression):
        if isinstance(raw_expression, raw_ast.String):
            return StrConstant(raw_expression.location, TYPES['Str'],
                               raw_expression.python_string)

        if isinstance(raw_expression, raw_ast.Integer):
            return IntConstant(raw_expression.location, TYPES['Int'],
                               raw_expression.python_int)

        if isinstance(raw_expression, raw_ast.FuncCall):
            call = self.cook_function_call(raw_expression)
            if call.function.type.returntype is None:
                raise common.CompileError(
                    "%s doesn't return a value" % call.function.type.name,
                    raw_expression.location)
            return call

        if isinstance(raw_expression, raw_ast.GetVar):
            varname = raw_expression.varname
            chef = self

            while True:
                if varname in chef.local_vars:
                    return LookupVar(
                        raw_expression.location, chef.local_vars[varname],
                        varname, chef.level)
                if chef.parent_chef is None:
                    raise common.CompileError(
                        "variable not found: %s" % varname,
                        raw_expression.location)

                chef = chef.parent_chef

        raise NotImplementedError("oh no: " + str(raw_expression))

    def cook_statement(self, raw_statement):
        if isinstance(raw_statement, raw_ast.Let):
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
                    return SetVar(
                        raw_statement.location, None,
                        varname, chef.level, cooked_value)
                if chef.parent_chef is None:
                    raise common.CompileError(
                        "variable not found: %s" % varname,
                        raw_expression.location)

                chef = chef.parent_chef

        if isinstance(raw_statement, raw_ast.FuncCall):
            return self.cook_function_call(raw_statement)

        if isinstance(raw_statement, raw_ast.FuncDefinition):
            if raw_statement.funcname in self.local_vars:
                raise common.CompileError(
                    ("there's already a variable named '%s'"
                     % raw_statement.funcname), raw_statement.location)
            functype = FunctionType(raw_statement.funcname)

            # TODO: allow functions to call themselves
            subchef = _Chef(self)
            body = list(map(subchef.cook_statement, raw_statement.body))
            self.local_vars[raw_statement.funcname] = functype
            return CreateLocalVar(
                raw_statement.location, functype, raw_statement.funcname,
                CreateFunction(raw_statement.location, functype,
                               raw_statement.funcname, body))

        assert False, raw_statement


def cook(raw_ast_statements):
    builtin_chef = _Chef(None)
    builtin_chef.local_vars['print'] = FunctionType('print', TYPES['Str'])
    return map(_Chef(builtin_chef).cook_statement, raw_ast_statements)
