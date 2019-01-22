from asdac import tokenizer, raw_ast
from asdac.raw_ast import (For, FuncCall, FuncFromGeneric, GetAttr,
                           GetType, GetVar, Let, SetVar, String,
                           TypeFromGeneric)
from asdac.common import CompileError, Location

import pytest


def parse(code):
    return list(raw_ast.parse(tokenizer.tokenize('test file', code)))


def test_not_an_expression_or_a_statement():
    with pytest.raises(CompileError) as error:
        parse('print(])')
    assert error.value.message == "expected an expression, got ']'"
    assert error.value.location == Location('test file', 1, 6, 1, 7)

    with pytest.raises(CompileError) as error:
        parse('"lol"')
    assert error.value.message == (
        "expected a let, a variable assignment, an if, a while, a function "
        "definition or a function call")
    assert error.value.location == Location('test file', 1, 0, 1, 5)


def test_generics():
    assert parse('magic_function[Str, Generator[Int]](x)') == [
        FuncCall(
            Location('test file', 1, 0, 1, 38),
            function=FuncFromGeneric(
                Location('test file', 1, 0, 1, 35),
                funcname='magic_function',
                types=[
                    GetType(Location('test file', 1, 15, 1, 18), name='Str'),
                    TypeFromGeneric(
                        Location('test file', 1, 20, 1, 34),
                        typename='Generator',
                        types=[
                            GetType(Location('test file', 1, 30, 1, 33),
                                    name='Int'),
                        ],
                    ),
                ],
            ),
            args=[GetVar(Location('test file', 1, 36, 1, 37), varname='x')]
        ),
    ]

    with pytest.raises(CompileError) as error:
        parse('lol[]')
    assert error.value.message == (
        "expected 1 or more comma-separated items, got 0")
    assert error.value.location == Location('test file', 1, 4, 1, 5)


def test_method_call():
    assert parse('"hello".uppercase()') == [
        FuncCall(
            Location('test file', 1, 0, 1, 19),
            function=GetAttr(
                Location('test file', 1, 0, 1, 17),
                obj=String(Location('test file', 1, 0, 1, 7),
                           python_string='hello'),
                attrname='uppercase',
            ),
            args=[],
        )
    ]


def test_for():
    assert parse('for let x = a; b; x = c:\n    print(x)') == [
        For(
            Location('test file', 1, 0, 1, 23),
            init=Let(
                Location('test file', 1, 4, 1, 13),
                varname='x',
                value=GetVar(Location('test file', 1, 12, 1, 13), varname='a'),
            ),
            cond=GetVar(Location('test file', 1, 15, 1, 16), varname='b'),
            incr=SetVar(
                Location('test file', 1, 18, 1, 23),
                varname='x',
                value=GetVar(Location('test file', 1, 22, 1, 23), varname='c'),
            ),
            body=[
                FuncCall(
                    Location('test file', 2, 4, 2, 12),
                    function=GetVar(Location('test file', 2, 4, 2, 9),
                                    varname='print'),
                    args=[GetVar(Location('test file', 2, 10, 2, 11),
                                 varname='x')],
                ),
            ],
        ),
    ]


def test_no_multiline_statement():
    with pytest.raises(CompileError) as error:
        parse('for while true:\n    print("hi")')
    assert error.value.message == "expected a one-line statement"
    assert error.value.location == Location('test file', 1, 4, 1, 14)


def test_assign_to_non_variable():
    with pytest.raises(CompileError) as error:
        parse('print("lol") = x')
    assert error.value.message == "expected a variable"
    assert error.value.location == Location('test file', 1, 0, 1, 12)


def test_repeated():
    with pytest.raises(CompileError) as error:
        parse('func lol[T, T]() -> void:\n    print("Boo")')
    assert error.value.message == "repeated generic type name: T"
    assert error.value.location == Location('test file', 1, 12, 1, 13)

    with pytest.raises(CompileError) as error:
        parse('func lol(Str x, Bool x) -> void:\n    print("Boo")')
    assert error.value.message == "repeated argument name: x"
    assert error.value.location == Location('test file', 1, 21, 1, 22)
