import functools

from asdac import raw_ast
from asdac.raw_ast import (For, FuncCall, FromGeneric, GetAttr,
                           GetType, GetVar, Let, SetVar, String)
from asdac.common import CompileError, Location

import pytest

location = functools.partial(Location, 'test file')


def parse(code):
    return list(raw_ast.parse('test file', code))


def test_not_an_expression_or_a_statement():
    with pytest.raises(CompileError) as error:
        parse('print(])')
    assert error.value.message == "expected an expression, got ']'"
    assert error.value.location == location(1, 6, 1, 7)

    with pytest.raises(CompileError) as error:
        parse('"lol"')
    assert error.value.message == (
        "expected a let, a variable assignment, an if, a while, a for, "
        "a return, a yield, a function definition or a function call")
    assert error.value.location == location(1, 0, 1, 5)


def test_parentheses_do_nothing(monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert (parse('let x = y') ==
            parse('let x = (y)') ==
            parse('let x = (((y)))'))


def test_invalid_operator_stuff():
    with pytest.raises(CompileError) as error:
        parse('let x = +1')
    assert error.value.message == "expected an expression, got '+'"
    assert error.value.location == location(1, 8, 1, 9)

    # TODO: this needs a better error message
    with pytest.raises(CompileError) as error:
        parse('let x = 1 + -2')
    assert error.value.message == "expected an expression, got '-'"
    assert error.value.location == location(1, 12, 1, 13)


def test_empty_string():
    [string] = parse('print("")')[0].args
    assert string.location == location(1, 6, 1, 8)
    assert string.python_string == ''


def test_empty_braces_in_string():
    with pytest.raises(CompileError) as error1:
        parse('print("{}")')
    with pytest.raises(CompileError) as error2:
        parse('print("{ }")')

    column = len('print("{')
    assert error1.value.message == "you must put some code between { and }"
    assert error2.value.message == "you must put some code between { and }"
    assert error1.value.location == location(1, column, 1, column)
    assert error2.value.location == location(1, column, 1, column+1)


# corner cases are handled in asdac.string_parser
def test_joined_strings():
    [string] = parse('print("a {b}")')[0].args
    assert isinstance(string, raw_ast.StrJoin)
    assert string.location == location(1, 6, 1, 13)

    a, b = string.parts
    assert a.location == location(1, 7, 1, 9)
    assert b.location == location(1, 10, 1, 11)

    assert isinstance(a, raw_ast.String)
    assert isinstance(b, raw_ast.FuncCall)      # implicit .to_string()


def test_generics():
    assert parse('magic_function[Str, Generator[Int]](x)') == [
        FuncCall(
            location(1, 0, 1, 38),
            function=FromGeneric(
                location(1, 0, 1, 35),
                name='magic_function',
                types=[
                    GetType(location(1, 15, 1, 18), name='Str'),
                    FromGeneric(
                        location(1, 20, 1, 34),
                        name='Generator',
                        types=[
                            GetType(location(1, 30, 1, 33),
                                    name='Int'),
                        ],
                    ),
                ],
            ),
            args=[GetVar(location(1, 36, 1, 37), varname='x')]
        ),
    ]

    with pytest.raises(CompileError) as error:
        parse('lol[]')
    assert error.value.message == (
        "expected 1 or more comma-separated items, got 0")
    assert error.value.location == location(1, 4, 1, 5)


def test_method_call():
    assert parse('"hello".uppercase()') == [
        FuncCall(
            location(1, 0, 1, 19),
            function=GetAttr(
                location(1, 0, 1, 17),
                obj=String(location(1, 0, 1, 7),
                           python_string='hello'),
                attrname='uppercase',
            ),
            args=[],
        )
    ]


def test_for():
    assert parse('for let x = a; b; x = c:\n    print(x)') == [
        For(
            location(1, 0, 1, 23),
            init=Let(
                location(1, 4, 1, 13),
                varname='x',
                value=GetVar(location(1, 12, 1, 13), varname='a'),
            ),
            cond=GetVar(location(1, 15, 1, 16), varname='b'),
            incr=SetVar(
                location(1, 18, 1, 23),
                varname='x',
                value=GetVar(location(1, 22, 1, 23), varname='c'),
            ),
            body=[
                FuncCall(
                    location(2, 4, 2, 12),
                    function=GetVar(location(2, 4, 2, 9),
                                    varname='print'),
                    args=[GetVar(location(2, 10, 2, 11),
                                 varname='x')],
                ),
            ],
        ),
    ]


def test_no_multiline_statement():
    with pytest.raises(CompileError) as error:
        parse('for while true:\n    print("hi")')
    assert error.value.message == "expected a one-line statement"
    assert error.value.location == location(1, 4, 1, 14)


def test_assign_to_non_variable():
    with pytest.raises(CompileError) as error:
        parse('print("lol") = x')
    assert error.value.message == "expected a variable"
    assert error.value.location == location(1, 0, 1, 12)


def test_repeated():
    with pytest.raises(CompileError) as error:
        parse('func lol[T, T]() -> void:\n    print("Boo")')
    assert error.value.message == "repeated generic type name: T"
    assert error.value.location == location(1, 12, 1, 13)

    with pytest.raises(CompileError) as error:
        parse('func lol(Str x, Bool x) -> void:\n    print("Boo")')
    assert error.value.message == "repeated argument name: x"
    assert error.value.location == location(1, 21, 1, 22)
