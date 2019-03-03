import functools
import itertools

from asdac import raw_ast
from asdac.raw_ast import (For, FuncCall, FromGeneric, GetAttr,
                           GetType, GetVar, Let, SetVar, String)
from asdac.common import Compilation, CompileError, Location

import pytest


# lol
class AnyCompilation(Compilation):
    def __init__(self): pass

    def __eq__(self, other): return isinstance(other, Compilation)


location = functools.partial(Location, AnyCompilation())


def test_not_an_expression_or_a_statement(compiler):
    compiler.doesnt_raw_parse('print(])', "syntax error", ']')


def test_dumb_statement(compiler):
    assert compiler.raw_parse('"lol"') == [String(location(0, 5), 'lol')]


def test_parentheses_do_nothing(compiler, monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert (compiler.raw_parse('let x = y') ==
            compiler.raw_parse('let x = (y)') ==
            compiler.raw_parse('let x = (((y)))'))


def test_backtick_function_call(compiler, monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    parse = compiler.raw_parse      # pep8 line length

    assert parse('x `f` y') == parse('f(x, y)')
    assert parse('(x `f` y) `g` z') == parse('g(f(x, y), z)')
    assert parse('x `f` (y `g` z)') == parse('f(x, g(y, z))')
    assert parse('x `f` y `g` z') == parse('(x `f` y) `g` z')
    assert parse('x `(f` y `g)` z') == parse('y(f, g)(x, z)')
    assert parse('x `f` y `g` z') != parse('x `(f` y `g)` z')


def test_prefix_minus(compiler, monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert compiler.raw_parse('x == -1') == compiler.raw_parse('x == (-1)')
    assert compiler.raw_parse('1 + -2 + 3 --4') == compiler.raw_parse(
        '1 + (-2) + 3 - (-4)')


def test_invalid_operator_stuff(compiler):
    compiler.doesnt_raw_parse('let x = +1', "syntax error", '+')
    for ops in itertools.product(['==', '!='], repeat=2):
        compiler.doesnt_raw_parse('x %s y %s z' % ops, "syntax error", ops[1])


def test_empty_string(compiler):
    [string] = compiler.raw_parse('print("")')[0].args
    assert string.location == location(6, 2)
    assert string.python_string == ''


def test_empty_braces_in_string(compiler):
    text = "you must put some code between { and }"

    compiler.doesnt_raw_parse('print("{ }")', text, ' ')

    # doesnt_raw_parse doesn't work for this because the location is empty
    with pytest.raises(CompileError) as error:
        compiler.raw_parse('print("{}")')
    assert error.value.message == text
    assert error.value.location == location(len('print("{'), 0)


def test_statement_in_braces(compiler):
    compiler.doesnt_raw_parse(
        'print("{let x = 1}")', "expected an expression, got a statement",
        'let x = 1')


# corner cases are handled in asdac.string_parser
def test_joined_strings(compiler):
    [string] = compiler.raw_parse('print("a {b}")')[0].args
    assert isinstance(string, raw_ast.StrJoin)
    assert string.location == location(6, 7)

    a, b = string.parts
    assert a.location == location(7, 2)
    assert b.location == location(10, 1)

    assert isinstance(a, raw_ast.String)
    assert isinstance(b, raw_ast.FuncCall)      # implicit .to_string()


def test_generics(compiler):
    assert compiler.raw_parse('magic_function[Str, Generator[Int]](x)') == [
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

    compiler.doesnt_raw_parse('lol[]', "syntax error", ']')


def test_method_call(compiler):
    assert compiler.raw_parse('"hello".uppercase()') == [
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


def test_for(compiler):
    assert compiler.raw_parse('for let x = a; b; x = c:\n    print(x)') == [
        For(
            location(0, 3),
            init=Let(
                location(4, 9),
                varname='x',
                value=GetVar(location(12, 1), varname='a'),
                export=False,
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


def test_no_multiline_statement(compiler):
    compiler.doesnt_raw_parse('for while true:\n    print("hi")',
                              "syntax error", 'while')


def test_assign_to_non_variable(compiler):
    compiler.doesnt_raw_parse('print("lol") = x', "syntax error", '=')


def test_repeated(compiler):
    compiler.doesnt_raw_parse('func lol[T, T]() -> void:\n    void',
                              "repeated generic type name: T", 'T')
    compiler.doesnt_raw_parse('func lol(Str x, Bool x) -> void:\n    void',
                              "repeated argument name: x", 'x')
