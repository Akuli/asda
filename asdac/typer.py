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
        this_function: Function,
        function_dict: typing.Dict[str, Function],
        local_vars: typing.Dict[str, Variable],
    ):
        self._this_function = this_function
        self._function_dict = function_dict
        self._local_vars = local_vars.copy()

    def _what_is_name(self, name: str) -> typing.Optional[str]:
        if name in BUILTIN_FUNCS:
            return "a built-in function"
        if name in BUILTIN_TYPES:
            return "a built-in type"
        if name in BUILTIN_VARS:
            return "a built-in variable"
        if name in self._function_dict:
            return "a function"
        if name in self._local_vars:
            return "a variable"
        return None

    def _check_name_doesnt_exist(self, name: str, location: Location) -> None:
        a_something = self._what_is_name(name)
        if a_something is not None:
            raise CompileError(
                f"there's already {a_something} named '{name}'", location)

    def _find_var(self, name: str, location: Location) -> Variable:
        if name in self._local_vars:
            return self._local_vars[name]
        if name in BUILTIN_VARS:
            return BUILTIN_VARS[name]

        a_something = self._what_is_name(name)
        if a_something is None:
            raise CompileError(f"no variable named '{name}'", location)
        raise CompileError(
            f"'{name}' is {a_something}, not a variable", location)

    def _find_func(self, name: str, location: Location) -> Function:
        if name in self._function_dict:
            return self._function_dict[name]
        if name in BUILTIN_FUNCS:
            return BUILTIN_FUNCS[name]

        a_something = self._what_is_name(name)
        if a_something is None:
            raise CompileError(f"no function named '{name}'", location)
        raise CompileError(
            f"'{name}' is {a_something}, not a function name", location)

    def _do_function_call(self, call: ast.CallFunction) -> ast.CallFunction:
        assert call.parser_ref is not None
        func = self._find_func(call.parser_ref.name, call.location)
        args = list(map(self.do_expression, call.args))

        if len(args) != len(func.argvars):
            raise CompileError(
                f"{func.get_string()} wants "
                f"{_arguments(len(func.argvars))}, but it was called with "
                f"{_arguments(len(args))}",
                call.location)

        for arg, argvar in zip(args, func.argvars):
            assert arg.type is not None
            if arg.type != argvar.type:
                raise CompileError(
                    f"expected {argvar.type.name}, got {arg.type.name}",
                    arg.location)

        return ast.CallFunction(
            call.location, func.returntype, call.parser_ref, func, args)

    def do_statement(self, statement: ast.Statement) -> ast.Statement:
        if isinstance(statement, ast.CallFunction):
            # TODO: warn about thrown away return value?
            return self._do_function_call(statement)

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

        if isinstance(statement, ast.SetVar):
            var = self._find_var(statement.parser_var.name, statement.location)
            value = self.do_expression(statement.value)
            assert value.type is not None
            if value.type != var.type:
                raise CompileError(
                    f"wrong types: "
                    f"{var.type.name} = {value.type.name}",
                    statement.location)

            return ast.SetVar(
                statement.location, var, statement.parser_var, value)

        if isinstance(statement, ast.Loop):
            # TODO: scope
            if statement.pre_cond is None:
                pre_cond = None
            else:
                pre_cond = self.do_expression(statement.pre_cond)

            body = list(map(self.do_statement, statement.body))

            if statement.post_cond is None:
                post_cond = None
            else:
                post_cond = self.do_expression(statement.post_cond)

            incr = list(map(self.do_statement, statement.incr))
            return ast.Loop(
                statement.location, pre_cond, post_cond, body, incr)

        if isinstance(statement, ast.Return):
            if statement.value is None:
                if self._this_function.returntype is not None:
                    raise CompileError(
                        f"this function must return a value "
                        f"of type {self._this_function.returntype.name}",
                        statement.location)
                return ast.Return(statement.location, None)

            if self._this_function.returntype is None:
                raise CompileError(
                    "this function must not return a value "
                    "because it has been defined with '-> void'",
                    statement.value.location)

            value = self.do_expression(statement.value)
            assert value.type is not None
            if value.type != self._this_function.returntype:
                raise CompileError(
                    f"should return a value of type "
                    f"{self._this_function.returntype.name}, "
                    f"not {value.type.name}",
                    statement.location)

            return ast.Return(statement.location, value)

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
                raise CompileError(
                    f"wrong types: "
                    f"{lhs.type.name} {expression.operator} {rhs.type.name}",
                    expression.location)

            assert func.returntype is not None
            result = ast.CallFunction(
                expression.location, func.returntype, None, func, [lhs, rhs])

            if negate:
                n0t = BUILTIN_FUNCS['not']
                result = ast.CallFunction(
                    expression.location, n0t.returntype, None, n0t, [result])

            return result

        elif isinstance(expression, ast.CallFunction):
            return self._do_function_call(expression)

        elif isinstance(expression, ast.StrJoin):
            parts = list(map(self.do_expression, expression.parts))
            for part in parts:
                if part.type != BUILTIN_TYPES['Str']:
                    raise CompileError(
                        f"should have type Str, not {part.type.name}",
                        part.type.location)

            return ast.StrJoin(
                expression.location, BUILTIN_TYPES['Str'], parts)

        else:
            raise NotImplementedError(expression)

    def do_expression(self, expression: ast.Expression) -> ast.Expression:
        result = self._do_expression_raw(expression)
        assert result.type is not None
        return result

    def do_function_body(
        self, statements: typing.List[ast.Statement],
    ) -> typing.List[ast.Statement]:

        result = list(map(self.do_statement, statements))
        if self._this_function.returntype is None:
            assert self._this_function.definition_location is not None
            result.append(ast.Return(
                self._this_function.definition_location, None))
        else:
            # TODO: put here something that triggers CompileError if it's ever
            #       reached
            pass

        return result


def _do_funcdef(
    funcdef: ast.FuncDefinition,
    function_dict: typing.Dict[str, Function],
) -> ast.FuncDefinition:

    function_object = function_dict[funcdef.parser_header.name]

    assert funcdef.function is None
    checker = _FunctionBodyTyper(function_object, function_dict, {
        var.name: var
        for var in function_dict[funcdef.parser_header.name].argvars
    })

    return ast.FuncDefinition(
        funcdef.location,
        funcdef.parser_header,
        function_object,
        checker.do_function_body(funcdef.body),
    )


def check_and_add_types(
    compilation: Compilation,
    funcdefs: typing.List[ast.FuncDefinition],
) -> typing.List[ast.FuncDefinition]:

    function_dict = _find_function_dict(funcdefs)
    return [_do_funcdef(funcdef, function_dict) for funcdef in funcdefs]
