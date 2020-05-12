"""Adds types to AST and checks that types are correct"""

import typing

import attr

from asdac import ast
from asdac.common import Compilation, CompileError, Location
from asdac.objects import (
    BUILTIN_FUNCS, BUILTIN_TYPES, BUILTIN_VARS,
    BUILTIN_PREFIX_OPERATORS, BUILTIN_BINARY_OPERATORS,
    Function, FunctionKind, Variable, VariableKind, Type)


def _duplicate_check(
    iterable: typing.Iterable[typing.Tuple[str, typing.Optional[Location]]],
    what_are_they: str,
) -> None:
    seen = set()
    for name, location in iterable:
        if name in seen:
            raise CompileError(
                f"repeated {what_are_they} name: {name}", location)
        seen.add(name)


def _do_type(tybe: ast.ParserType) -> Type:
    if tybe.name in BUILTIN_TYPES:
        return BUILTIN_TYPES[tybe.name]
    raise CompileError(f"no type named '{tybe.name}'", tybe.location)


# two passes, first we find types of all functions and then parse their
# body codes. This way functions can call other functions that are defined
# later in the file, or they can call themselves.

def _find_function_dict(
    funcdefs: typing.List[ast.FuncDefinition],
) -> typing.Dict[str, Function]:

    result: typing.Dict[str, Function] = {}

    for funcdef in funcdefs:
        header = funcdef.parser_header

        if funcdef.parser_header.name in BUILTIN_FUNCS:
            raise CompileError(
                "there is already a built-in function"
                f"named '{funcdef.parser_header.name}'",
                funcdef.location)
        if funcdef.parser_header.name in result:
            raise CompileError(
                f"there are two functions named '{header.name}' "
                "in the same file", funcdef.location)

        argvars = [
            Variable(arg.name, _do_type(arg.type),
                     VariableKind.LOCAL, arg.location)
            for arg in header.args
        ]
        _duplicate_check(
            ((var.name, var.definition_location) for var in argvars),
            "argument")

        if header.returntype is None:
            returntype = None
        else:
            returntype = _do_type(header.returntype)

        result[header.name] = Function(
            header.name, argvars, returntype,
            FunctionKind.FILE, funcdef.location)

    if 'main' not in result:
        raise CompileError("""\
you must define a main function, e.g:

    function main() -> void:
        ...""")

    result['main'] = attr.evolve(result['main'], is_main=True)

    return result


def _arguments(n: int) -> str:
    return ("no arguments" if n == 0 else
            "1 argument" if n == 1 else
            f"{n} arguments")


class _FunctionBodyTyper:

    def __init__(
        self,
        function_dict: typing.Dict[str, Function],
        local_vars: typing.Dict[str, Variable],
    ):
        self._function_dict = function_dict
        self._local_vars = local_vars.copy()

    def _check_name_doesnt_exist(self, name: str, location: Location) -> None:
        if name in BUILTIN_FUNCS:
            its = "a built-in function"
        elif name in BUILTIN_TYPES:
            its = "a built-in type"
        elif name in BUILTIN_VARS:
            its = "a built-in variable"
        elif name in self._function_dict:
            its = "a function"
        elif name in self._local_vars:
            its = "a variable"
        else:
            return

        raise CompileError(
            f"there's already {its} named '{name}'", location)

    def do_statement(self, statement: ast.Statement) -> ast.Statement:
        if isinstance(statement, ast.CallFunction):
            assert statement.parser_ref is not None
            if statement.parser_ref.name in BUILTIN_FUNCS:
                func = BUILTIN_FUNCS[statement.parser_ref.name]
            elif statement.parser_ref.name in self._function_dict:
                func = self._function_dict[statement.parser_ref.name]
            else:
                raise CompileError(
                    f"function not found: {statement.parser_ref.name}",
                    statement.location)

            args = list(map(self.do_expression, statement.args))

            if len(args) != len(func.argvars):
                raise CompileError(
                    f"{func.get_string()} wants "
                    f"{_arguments(len(func.argvars))}, but it was called with "
                    f"{_arguments(len(args))}",
                    statement.location)

            for arg, argvar in zip(args, func.argvars):
                assert arg.type is not None
                if arg.type != argvar.type:
                    raise CompileError(
                        f"expected {argvar.type.name}, got {arg.type.name}",
                        arg.location)

            # TODO: warn about thrown away return value?
            return ast.CallFunction(
                statement.location, func.returntype, statement.parser_ref,
                func, args)

        if isinstance(statement, ast.Let):
            self._check_name_doesnt_exist(
                statement.parser_var.name, statement.location)
            initial_value = self.do_expression(statement.initial_value)
            assert initial_value.type is not None
            var = Variable(statement.parser_var.name, initial_value.type,
                           VariableKind.LOCAL, statement.location)
            self._local_vars[statement.parser_var.name] = var
            return ast.Let(
                statement.location, var, statement.parser_var, initial_value)

        if isinstance(statement, ast.IfStatement):
            cond = self.do_expression(statement.cond)
            assert cond.type is not None
            if cond.type != BUILTIN_TYPES['Bool']:
                raise CompileError(
                    f"expected Bool, got {cond.type.name}", cond.location)

            if_body = list(map(self.do_statement, statement.if_body))
            else_body = list(map(self.do_statement, statement.else_body))
            return ast.IfStatement(
                statement.location, cond, if_body, else_body)

        if isinstance(statement, ast.Throw):
            return statement

        raise NotImplementedError(statement)

    def _do_expression_raw(self, expression: ast.Expression) -> ast.Expression:
        # TODO: function call expressions (remember to check for void-return)
        if isinstance(expression, ast.StrConstant):
            assert expression.type is BUILTIN_TYPES['Str']
            return expression

        if isinstance(expression, ast.IntConstant):
            assert expression.type is BUILTIN_TYPES['Int']
            return expression

        if isinstance(expression, ast.GetVar):
            name = expression.parser_var.name
            if name in self._local_vars:
                var = self._local_vars[name]
            elif name in BUILTIN_VARS:
                var = BUILTIN_VARS[name]
            else:
                raise CompileError(
                    f"no variable named '{name}'", expression.location)

            return ast.GetVar(
                expression.location, var.type, var, expression.parser_var)

        elif isinstance(expression, ast.PrefixOperation):
            prefixed = self.do_expression(expression.prefixed)
            assert prefixed.type is not None

            try:
                func = BUILTIN_PREFIX_OPERATORS[(
                    expression.operator, prefixed.type)]
            except KeyError:
                raise CompileError(
                    f"wrong types: {expression.operator}{prefixed.type.name}",
                    expression.location)

            assert func.returntype is not None
            return ast.CallFunction(
                expression.location, func.returntype, None, func, [prefixed])

        elif isinstance(expression, ast.BinaryOperation):
            lhs = self.do_expression(expression.lhs)
            rhs = self.do_expression(expression.rhs)

            if expression.operator == '!=':
                operator = '=='
                negate = True
            else:
                operator = expression.operator
                negate = False

            assert lhs.type is not None
            assert rhs.type is not None
            try:
                func = BUILTIN_BINARY_OPERATORS[(
                    lhs.type, operator, rhs.type)]
            except KeyError:
                print(BUILTIN_BINARY_OPERATORS.keys())
                print(lhs.type, operator, rhs.type)
                raise CompileError(
                    f"wrong types: "
                    f"{lhs.type.name} {expression.operator} {rhs.type.name}",
                    expression.location)

            assert func.returntype is not None
            result = ast.CallFunction(
                expression.location, func.returntype, None,
                func, [expression.lhs, expression.rhs])

            if negate:
                n0t = BUILTIN_FUNCS['not']
                result = ast.CallFunction(
                    expression.location, n0t.returntype, None, n0t, [result])

            return result

        raise NotImplementedError(expression)

    def do_expression(self, expression: ast.Expression) -> ast.Expression:
        result = self._do_expression_raw(expression)
        assert result.type is not None
        return result


def _do_funcdef(
    funcdef: ast.FuncDefinition,
    function_dict: typing.Dict[str, Function],
) -> ast.FuncDefinition:

    assert funcdef.function is None
    checker = _FunctionBodyTyper(function_dict, {
        var.name: var
        for var in function_dict[funcdef.parser_header.name].argvars
    })

    return ast.FuncDefinition(
        funcdef.location,
        funcdef.parser_header,
        function_dict[funcdef.parser_header.name],
        list(map(checker.do_statement, funcdef.body)),
    )


def check_and_add_types(
    compilation: Compilation,
    funcdefs: typing.List[ast.FuncDefinition],
) -> typing.List[ast.FuncDefinition]:

    function_dict = _find_function_dict(funcdefs)
    return [_do_funcdef(funcdef, function_dict) for funcdef in funcdefs]
