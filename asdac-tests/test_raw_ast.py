import functools
import itertools

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
    assert error.value.message == "syntax error"
    assert error.value.location == location(6, 1)


def test_dumb_statement():
    assert parse('"lol"') == [String(location(0, 5), 'lol')]


def test_parentheses_do_nothing(monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert (parse('let x = y') ==
            parse('let x = (y)') ==
            parse('let x = (((y)))'))


def test_backtick_function_call(monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert parse('x `f` y') == parse('f(x, y)')
    assert parse('(x `f` y) `g` z') == parse('g(f(x, y), z)')
    assert parse('x `f` (y `g` z)') == parse('f(x, g(y, z))')
    assert parse('x `f` y `g` z') == parse('(x `f` y) `g` z')
    assert parse('x `(f` y `g)` z') == parse('y(f, g)(x, z)')
    assert parse('x `f` y `g` z') != parse('x `(f` y `g)` z')


def test_prefix_minus(monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert parse('x == -1') == parse('x == (-1)')
    assert parse('1 + -2 + 3 --4') == parse('1 + (-2) + 3 - (-4)')


def test_invalid_operator_stuff():
    with pytest.raises(CompileError) as error:
        parse('let x = +1')
    assert error.value.message == "syntax error"
    assert error.value.location == location(8, 1)

    for ops in itertools.product(['==', '!='], repeat=2):
        with pytest.raises(CompileError) as error:
            parse('x %s y %s z' % ops)
        assert error.value.message == "syntax error"
        assert error.value.location == location(7, 2)


def test_empty_string():
    [string] = parse('print("")')[0].args
    assert string.location == location(6, 2)
    assert string.python_string == ''


def test_empty_braces_in_string():
    with pytest.raises(CompileError) as error1:
        parse('print("{}")')
    with pytest.raises(CompileError) as error2:
        parse('print("{ }")')

    column = len('print("{')
    assert error1.value.message == "you must put some code between { and }"
    assert error2.value.message == "you must put some code between { and }"
    assert error1.value.location == location(column, 0)
    assert error2.value.location == location(column, 1)


# corner cases are handled in asdac.string_parser
def test_joined_strings():
    [string] = parse('print("a {b}")')[0].args
    assert isinstance(string, raw_ast.StrJoin)
    assert string.location == location(6, 7)

    a, b = string.parts
    assert a.location == location(7, 2)
    assert b.location == location(10, 1)

    assert isinstance(a, raw_ast.String)
    assert isinstance(b, raw_ast.FuncCall)      # implicit .to_string()


def test_generics():
    assert parse('magic_function[Str, Generator[Int]](x)') == [
        FuncCall(
            location(35, 3),
            function=FromGeneric(
                location(0, 35),
                name='magic_function',
                types=[
                    GetType(location(15, 3), name='Str'),
                    FromGeneric(
                        location(20, 14),
                        name='Generator',
                        types=[
                            GetType(location(30, 3),
                                    name='Int'),
                        ],
                    ),
                ],
            ),
            args=[GetVar(location(36, 1), varname='x')]
        ),
    ]

    with pytest.raises(CompileError) as error:
        parse('lol[]')
    assert error.value.message == "syntax error"
    assert error.value.location == location(4, 1)


def test_method_call():
    assert parse('"hello".uppercase()') == [
        FuncCall(
            location(17, 2),
            function=GetAttr(
                location(7, 1),
                obj=String(location(0, 7),
                           python_string='hello'),
                attrname='uppercase',
            ),
            args=[],
        )
    ]


def test_for():
    assert parse('for let x = a; b; x = c:\n    print(x)') == [
        For(
            location(0, 3),
            init=Let(
                location(4, 9),
                varname='x',
                value=GetVar(location(12, 1), varname='a'),
            ),
            cond=GetVar(location(15, 1), varname='b'),
            incr=SetVar(
                location(18, 5),
                varname='x',
                value=GetVar(location(22, 1), varname='c'),
            ),
            body=[
                FuncCall(
                    location(34, 3),
                    function=GetVar(location(29, 5),
                                    varname='print'),
                    args=[GetVar(location(35, 1),
                                 varname='x')],
                ),
            ],
        ),
    ]


def test_no_multiline_statement():
    with pytest.raises(CompileError) as error:
        parse('for while true:\n    print("hi")')
    assert error.value.message == "syntax error"
    assert error.value.location == location(4, 5)


def test_assign_to_non_variable():
    with pytest.raises(CompileError) as error:
        parse('print("lol") = x')
    assert error.value.message == "syntax error"
    assert error.value.location == location(13, 1)


def test_repeated():
    with pytest.raises(CompileError) as error:
        parse('func lol[T, T]() -> void:\n    print("Boo")')
    assert error.value.message == "repeated generic type name: T"
    assert error.value.location == location(12, 1)

    with pytest.raises(CompileError) as error:
        parse('func lol(Str x, Bool x) -> void:\n    print("Boo")')
    assert error.value.message == "repeated argument name: x"
    assert error.value.location == location(21, 1)
