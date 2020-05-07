import collections
import enum
import typing

import attr

from asdac import common, raw_ast, objects


class VariableKind(enum.Enum):
    BUILTIN = 0
    LOCAL = 1

class FunctionKind(enum.Enum):
    BUILTIN = 0
    FILE = 1


# all variables are local variables for now.
# note that there is code that uses copy.copy() with Variable objects
@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Variable:
    name: str
    type: objects.Type
    kind: VariableKind
    definition_location: typing.Optional[common.Location]

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Function:
    name: str
    argvars: typing.List[Variable]
    returntype: typing.Optional[objects.Type]
    kind: FunctionKind
    definition_location: typing.Optional[common.Location]
    is_main: bool = False

    def get_string(self) -> str:
        return '%s(%s)' % (self.name, ', '.join(
            self.argvars[0].type.name + ' ' + self.argvars[0].name))
            

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Statement:
    location: common.Location

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Expression(Statement):
    location: common.Location
    # this is optional because a function might return void (nothing reasonable
    # to put here), and function calls are expressions.
    #
    # I could also separate void-function calls and non-void function calls but
    # why bother?
    type: typing.Optional[objects.Type]

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class StrConstant(Expression):
    python_string: str

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class StrJoin(Expression):
    parts: typing.List[Expression]

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class IntConstant(Expression):
    python_int: int

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class GetVar(Expression):
    var: Variable

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class SetVar(Statement):
    var: Variable

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class FuncDefinition(Statement):
    function: Function
    body: typing.List[Statement]

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class CallFunction(Expression, Statement):
    function: Function
    args: typing.List[Expression]

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Return(Statement):
    value: typing.Optional[Expression]

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class IfStatement(Statement):
    cond: Expression
    if_body: typing.List[Statement]
    else_body: typing.List[Statement]

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class IfExpression(Expression):
    cond: Expression
    true_expr: Expression
    false_expr: Expression

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Loop(Statement):
    pre_cond: Expression
    post_cond: Expression
    incr: typing.List[Statement]
    body: typing.List[Statement]


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


def _cook_type(raw_type: typing.Any) -> objects.Type:
    # TODO: functype, generic type, user-defined type
    assert isinstance(raw_type, typing.cast(typing.Any, raw_ast).GetType)
    try:
        return objects.BUILTIN_TYPES[raw_type.name]
    except KeyError:
        raise common.CompileError(
            "there is no type named '%s'" % raw_type.name)


class FileChef:

    def __init__(self) -> None:
        self.functions: typing.Dict[str, Function] = {}     # {name: Function}
        self.function_bodies: typing.Dict[str, typing.List[Statement]] = {}

    # two passes, first we find all functions and then parse them. This way
    # functions can call other functions that are defined later in the file, or
    # they can call themselves.
    def discover_function(self, funcdef: typing.Any) -> None:
        assert isinstance(funcdef,
                          typing.cast(typing.Any, raw_ast).FuncDefinition)
        if funcdef.name in self.functions:
            raise common.CompileError(
                "there are two functions named '%s'" % funcdef.name,
                funcdef.location)

        raw_args, raw_returntype = funcdef.header
        assert not raw_args     # TODO
        returntype = (None if raw_returntype is None
                      else _cook_type(raw_returntype))

        self.functions[funcdef.name] = Function(
            funcdef.name, [], returntype, FunctionKind.FILE, funcdef.location,
            # TODO: check that there is main, don't allow multiple mains, etc.
            #       Or get rid of main function altogether?
            is_main=(funcdef.name == 'main'))

    def cook_function_definition(self, funcdef: typing.Any) -> FuncDefinition:
        assert isinstance(funcdef,
                          typing.cast(typing.Any, raw_ast).FuncDefinition)
        subchef = FunctionChef(self.functions)
        return FuncDefinition(
            funcdef.location,
            self.functions[funcdef.name],
            list(map(subchef.cook_statement, funcdef.body)),
        )


class FunctionChef:

    def __init__(self, file_functions: typing.Dict[str, Function]):
        self.functions: typing.Dict[str, Function] = {}
        self.functions.update(BUILTIN_FUNCS)
        self.functions.update(file_functions)
        self.local_vars: typing.Dict[str, Variable] = {}

    def _cook_arguments(
            self,
            func: Function,
            raw_args: typing.List[typing.Any],
            error_location: common.Location) -> typing.List[Expression]:
        args = [self.cook_expression(arg) for arg in raw_args]
        if [arg.type for arg in args] != [var.type for var in func.argvars]:
            raise common.CompileError(
                "cannot call %s(%s) with arguments of types %s" % (
                    func.name,
                    ', '.join(var.type.name for var in func.argvars),
                    ', '.join(arg.type.name for arg in raw_args),
                ), error_location)

        return args

    def cook_statement(self, statement: typing.Any) -> Statement:
        if isinstance(statement, typing.cast(typing.Any, raw_ast).FuncCall):
            return self.cook_function_call(statement)
        raise NotImplementedError

    def cook_function_call(
            self, raw_func_call: typing.Any) -> CallFunction:
        assert isinstance(raw_func_call,
                          typing.cast(typing.Any, raw_ast).FuncCall)

        # TODO: function objects
        if not isinstance(raw_func_call.function,
                          typing.cast(typing.Any, raw_ast).GetVar):
            raise common.CompileError(
                "invalid function name", raw_func_call.function.location)

        func = self.functions[raw_func_call.function.varname]
        args = self._cook_arguments(
            func, raw_func_call.args, raw_func_call.location)

        return CallFunction(
            raw_func_call.location, func.returntype, func, args)

    # never returns an Expression whose .type is None (aka a void-returning
    # function call)
    def cook_expression(self, raw_expression: typing.Any) -> Expression:
        if isinstance(raw_expression, typing.cast(typing.Any, raw_ast).String):
            return StrConstant(raw_expression.location,
                               objects.BUILTIN_TYPES['Str'],
                               raw_expression.python_string)

        if isinstance(raw_expression,
                      typing.cast(typing.Any, raw_ast).Integer):
            return IntConstant(raw_expression.location,
                               objects.BUILTIN_TYPES['Int'],
                               raw_expression.python_int)

        if isinstance(raw_expression,
                      typing.cast(typing.Any, raw_ast).FuncCall):
            call = self.cook_function_call(raw_expression)
            if call.function.returntype is None:
                raise common.CompileError(
                    "this function doesn't return a value",
                    raw_expression.location)
            return call

        if isinstance(raw_expression, typing.cast(typing.Any, raw_ast).GetVar):
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

        if isinstance(raw_expression,
                      typing.cast(typing.Any, raw_ast).StrJoin):
            return StrJoin(
                raw_expression.location, objects.BUILTIN_TYPES['Str'],
                list(map(self.cook_expression, raw_expression.parts)))

        if isinstance(raw_expression, typing.cast(typing.Any, raw_ast).IfExpression):
            cond = self.cook_expression(raw_expression.cond)
            assert cond.type is not None
            if cond.type is not objects.BUILTIN_TYPES['Bool']:
                raise common.CompileError(
                    "expected Bool, got " + cond.type.name, cond.location)

            true_expr = self.cook_expression(raw_expression.true_expr)
            false_expr = self.cook_expression(raw_expression.false_expr)
            assert true_expr.type is not None
            assert false_expr.type is not None

            if true_expr.type != false_expr.type:
                raise common.CompileError(
                    "'then' value has type %s, but 'else' value has type %s"
                    % (true_expr.type.name, false_expr.type.name),
                    raw_expression.location)
            return IfExpression(raw_expression.location, true_expr.type,
                                cond, true_expr, false_expr)

        raise NotImplementedError(raw_expression)   # pragma: no cover


def cook(
    compilation: common.Compilation,
    raw_statements: typing.List[typing.Any]
) -> typing.List[FuncDefinition]:
    chef = FileChef()

    for funcdef in raw_statements:
        assert isinstance(funcdef, typing.cast(typing.Any, raw_ast).FuncDefinition)
        chef.discover_function(funcdef)

    return list(map(chef.cook_function_definition, raw_statements))
