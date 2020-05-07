import collections
import enum
import typing

from asdac import common, raw_ast, objects


class VariableKind(enum.Enum):
    BUILTIN = 0
    LOCAL = 1


class FunctionKind(enum.Enum):
    BUILTIN = 0
    FILE = 1


def _astclass(name, fields):
    # type is set to None for statements
    return collections.namedtuple(name, ['location', 'type'] + fields)


StrConstant = _astclass('StrConstant', ['python_string'])
StrJoin = _astclass('StrJoin', ['parts'])  # there are always >=2 parts
IntConstant = _astclass('IntConstant', ['python_int'])
GetVar = _astclass('GetVar', ['var'])
SetVar = _astclass('SetVar', ['var', 'value'])
FuncDefinition = _astclass('FuncDefinition', ['function', 'body'])
CreateLocalVar = _astclass('CreateLocalVar', ['var'])
CallFunction = _astclass('CallFunction', ['function', 'args'])
Return = _astclass('Return', ['value'])    # value can be None
IfStatement = _astclass('IfStatement', ['cond', 'if_body', 'else_body'])
IfExpression = _astclass('IfExpression', ['cond', 'true_expr', 'false_expr'])
Loop = _astclass('Loop', ['pre_cond', 'post_cond', 'incr', 'body'])


# all variables are local variables for now.
# note that there is code that uses copy.copy() with Variable objects
class Variable:

    def __init__(self, name, tybe, kind, definition_location):
        self.name = name
        self.type = tybe
        self.kind = kind
        self.definition_location = definition_location    # can be None

    def __repr__(self):
        return '<%s %r>' % (type(self).__name__, self.name)


class Function:

    def __init__(self,
                 name: str,
                 argvars: typing.List[Variable],
                 returntype: typing.Optional[objects.Type],
                 kind: FunctionKind,
                 definition_location: common.Location,
                 *,
                 is_main: bool = False):
        self.name = name
        self.argvars = argvars
        self.returntype = returntype    # may be None
        self.kind = kind
        self.definition_location = definition_location    # can be None
        self.is_main = is_main

    def __repr__(self):
        return '<%s: %s(%s) -> %s>' % (
            type(self).__name__, self.name,
            ', '.join(var.type.name + ' ' + var.name for var in self.argvars),
            'void' if self.returntype is None else self.returntype.name,
        )


BUILTIN_VARS = {
    name: Variable(name, tybe, VariableKind.BUILTIN, None)
    for name, tybe in objects.BUILTIN_VARS.items()
}
BUILTIN_FUNCS = {
    name: Function(
        name,
        [
            Variable('arg' + str(index), tybe, VariableKind.LOCAL, None)
            for index, tybe in enumerate(argtypes, start=1)
        ],
        returntype,
        FunctionKind.BUILTIN,
        None,
    )
    for name, (argtypes, returntype) in objects.BUILTIN_FUNCS.items()
}


class Chef:

    def cook_type(self, raw_type):
        assert isinstance(raw_type, raw_ast.GetType)    # TODO: functype
        try:
            return self.types[raw_type.name]
        except KeyError:
            raise common.CompileError(
                "there is no type named '%s'" % raw_type.name)


class FileChef(Chef):

    def __init__(self):
        self.functions = {}     # {name: Function}
        self.function_bodies = {}

    # two passes, first we find all functions and then parse them. This way
    # functions can call other functions that are defined later in the file, or
    # they can call themselves.
    def discover_function(self, funcdef: raw_ast.FuncDefinition):
        if funcdef.name in self.functions:
            raise common.CompileError(
                "there are two functions named '%s'" % funcdef.name,
                funcdef.location)

        raw_args, raw_returntype = funcdef.header
        assert not raw_args     # TODO
        returntype = (None if raw_returntype is None
                      else self.cook_type(raw_returntype))

        self.functions[funcdef.name] = Function(
            funcdef.name, [], returntype, FunctionKind.FILE, funcdef.location,
            # TODO: check that there is main, don't allow multiple mains, etc.
            #       Or get rid of main function altogether?
            is_main=(funcdef.name == 'main'))

    def cook_function_definition(self, funcdef: raw_ast.FuncDefinition):
        subchef = FunctionChef(self.functions)
        return FuncDefinition(
            funcdef.location,
            None,
            self.functions[funcdef.name],
            list(map(subchef.cook_statement, funcdef.body)),
        )


class FunctionChef(Chef):

    def __init__(self, file_functions):
        self.functions = {}
        self.functions.update(BUILTIN_FUNCS)
        self.functions.update(file_functions)
        self.local_vars = {}    # {name: Variable}

    def _get_arguments_message(self, types):
        if len(types) >= 2:
            return "arguments of types (%s)" % ', '.join(t.name for t in types)
        if len(types) == 1:
            return "one argument of type %s" % types[0].name
        assert not types
        return "no arguments"

    def _cook_arguments(self, func: Function, raw_args, error_location):
        args = [self.cook_expression(arg) for arg in raw_args]
        if [arg.type for arg in args] != [var.type for var in func.argvars]:
            raise common.CompileError(
                "cannot call %s(%s) with arguments of types %s" % (
                    name,
                    ', '.join(var.type.name for var in func.argvars),
                    ', '.join(arg.type.name for arg in raw_args),
                ), error_location)

        return args

    def cook_statement(self, statement):
        if isinstance(statement, raw_ast.FuncCall):
            return self.cook_function_call(statement)
        raise NotImplementedError

    def cook_function_call(self, raw_func_call: raw_ast.FuncCall):
        # TODO: function objects
        if not isinstance(raw_func_call.function, raw_ast.GetVar):
            raise common.CompileError(
                "invalid function name", function.location)

        print(self.functions)
        func = self.functions[raw_func_call.function.varname]
        args = self._cook_arguments(
            func, raw_func_call.args, raw_func_call.location)

        return CallFunction(
            raw_func_call.location, func.returntype, func, args)

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
                tybe = obj.type.attributes[raw_expression.attrname].type
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
            assert raw_expression.module_path is None   # TODO
            assert raw_expression.generics is None      # TODO

            try:
                var = self.local_vars[raw_expression.varname]
            except KeyError:
                try:
                    var = BUILTIN_VARS[raw_expression.varname]
                except KeyError:
                    raise common.CompileError(
                        "no variable named '%s'" % raw_expression.varname)

            return GetVar(raw_expression.location, var.type, var)

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

        raise NotImplementedError(raw_expression)   # pragma: no cover


def cook(compilation, raw_statements, import_compilation_dict):
    # TODO: imports and exports
    assert not import_compilation_dict

    chef = FileChef()

    for funcdef in raw_statements:
        assert isinstance(funcdef, raw_ast.FuncDefinition)
        chef.discover_function(funcdef)

    result = list(map(chef.cook_function_definition, raw_statements))
    return (result, collections.OrderedDict())
