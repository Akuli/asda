import functools
import itertools

from asdac import raw_ast
from asdac.raw_ast import (For, FuncCall, GetAttr, Integer, IfStatement,
                           GetType, GetVar, Let, SetVar, String)
from asdac.common import CompileError, Location

import pytest


class Any:
    def __repr__(self):
        return 'Any()'

    def __eq__(self, other):
        return True


location = functools.partial(Location, Any())


def test_invalid_statement(compiler):
    compiler.doesnt_raw_parse('"lol"', "invalid statement", '"lol"')


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

    compiler.doesnt_raw_parse(
        'x ` y', "should be: expression `expression` expression", '`')


def test_precedence_and_chaining(compiler, monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))

    # raw_parse wants statements, not just expressions
    # wrapping everything in f() creates statements

    assert (compiler.raw_parse('f(x == -1)') ==
            compiler.raw_parse('f(x == (-1))'))
    assert (compiler.raw_parse('f(1 - 2 + 3 - 4)') ==
            compiler.raw_parse('f( ((1 - 2) + 3) - 4 )'))
    assert (compiler.raw_parse('f(1 - 2 + 3 - 4)') !=
            compiler.raw_parse('f((1 - 2) + (3 - 4))'))
    assert (compiler.raw_parse('f(1 - 2 + 3 - 4)') !=
            compiler.raw_parse('f( 1 - (2 + (3 - 4)) )'))

    compiler.raw_parse('f(-(-x))')
    compiler.doesnt_raw_parse(
        'f(--x)', "'-' cannot be used like this", '-', rindex=False)

    compiler.raw_parse('f((x == y) == z)')


def test_confusing_operator_chaining_disallowed(compiler):
    for ops in itertools.product(['==', '!='], repeat=2):
        compiler.doesnt_raw_parse(
            'x %s y %s z' % ops,
            "'a %s b %s c' is not valid syntax" % ops,
            ops[1])


def test_invalid_operator_stuff(compiler):
    compiler.raw_parse('let x = -1')
    compiler.doesnt_raw_parse('let x = +1',
                              "'+' cannot be used like this", '+')


def test_empty_string(compiler):
    [string] = compiler.raw_parse('print("")')[0].args
    assert string.location == location(6, 2)
    assert string.python_string == ''


def test_braces_errors(compiler):
    text = "you must put some code between { and }"

    compiler.doesnt_raw_parse('print("{ }")', text, ' ')

    # doesnt_raw_parse doesn't work for this because the location is empty
    with pytest.raises(CompileError) as error:
        compiler.raw_parse('print("{}")')
    assert error.value.message == text
    assert error.value.location == location(len('print("{'), 0)

    compiler.doesnt_raw_parse(
        'import "{x}" as y', "cannot use {...} strings here", 'x')
    compiler.doesnt_raw_parse(
        '"{123 then blah}"', "invalid syntax", 'then blah')


def test_statement_in_braces(compiler):
    compiler.doesnt_raw_parse(
        'print("{let x = 1}")', "should be an expression", 'let')


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
    [fc] = compiler.raw_parse('magic_function[Str, Array[Int]](x)')
    assert fc == FuncCall(
        location=Any(),
        function=GetVar(
            location=Any(),
            module_path=None,
            varname='magic_function',
            generics=[
                GetType(
                    location=Any(),
                    name='Str',
                    generics=None,
                ),
                GetType(
                    location=Any(),
                    name='Array',
                    generics=[
                        GetType(
                            location=Any(),
                            name='Int',
                            generics=None,
                        ),
                    ],
                ),
            ],
        ),
        args=[
            GetVar(
                module_path=None,
                location=Any(),
                varname='x',
                generics=None,
            ),
        ],
    )


def test_generics_empty_error(compiler):
    compiler.doesnt_raw_parse(
        'lol[]', "you must put something between '[' and ']'", '[]')
    compiler.doesnt_raw_parse(
        'let x[] = 1', "you must put something between '[' and ']'", '[]')
    compiler.doesnt_raw_parse(
        '(lol[] x) -> void:\n a',
        "you must put something between '[' and ']'", '[]')


def test_method_call(compiler):
    [fc] = compiler.raw_parse('"hello".uppercase(1)(2)')
    assert fc == FuncCall(
        location=Any(),
        function=FuncCall(
            location=Any(),
            function=GetAttr(
                location=Any(),
                obj=String(
                    location=Any(),
                    python_string='hello',
                ),
                attrname='uppercase',
            ),
            args=[Integer(location=Any(), python_int=1)],
        ),
        args=[Integer(location=Any(), python_int=2)],
    )


def test_for(compiler):
    [four] = compiler.raw_parse('for let x = a; b; x = c:\n    print(x)')
    assert four == For(
        location=Location(Any(), 0, 3),
        init=Let(
            location=Location(Any(), 4, 3),
            varname='x',
            generics=None,
            value=GetVar(
                module_path=None,
                location=Location(Any(), 12, 1),
                varname='a',
                generics=None,
            ),
            export=False,
            outer=False,
        ),
        cond=GetVar(
            module_path=None,
            location=Location(Any(), 15, 1),
            varname='b',
            generics=None,
        ),
        incr=SetVar(
            location=Location(Any(), 20, 1),
            varname='x',
            value=GetVar(
                module_path=None,
                location=Location(Any(), 22, 1),
                varname='c',
                generics=None,
            ),
        ),
        body=[
            FuncCall(
                location=Location(Any(), 29, 8),
                function=GetVar(
                    module_path=None,
                    location=Location(Any(), 29, 5),
                    varname='print',
                    generics=None,
                ),
                args=[
                    GetVar(
                        module_path=None,
                        location=Location(Any(), 35, 1),
                        varname='x',
                        generics=None,
                    ),
                ],
            ),
        ],
    )


def test_should_be_a(compiler):
    # no expression or statement begins with a comma
    compiler.doesnt_raw_parse('let x = ,',
                              "should be an expression", ',')
    compiler.doesnt_raw_parse('for let x = 1; x != 10; ,:',
                              "should be a one-line statement", ',')
    compiler.doesnt_raw_parse(',',
                              "should be a statement", ',')


def test_assign_to_non_variable(compiler):
    compiler.doesnt_raw_parse('print("lol") = x', "invalid assignment", '=')


def test_repeated(compiler):
    compiler.doesnt_raw_parse('let lol[T, T] = () -> void:\n    void',
                              "repeated generic type name: T", 'T')
    compiler.doesnt_raw_parse('let lol = (Str x, Bool x) -> void:\n    void',
                              "repeated argument name: x", 'Bool x')


def test_invalid_this_or_that(compiler):
    compiler.doesnt_raw_parse('let f = ("hey" x) -> void:\n blah',
                              "invalid type", '"hey"')
    compiler.doesnt_raw_parse('let f = (Str "hey") -> void:\n blah',
                              "invalid variable name", '"hey"')


def test_wrong_token_errors(compiler):
    compiler.doesnt_raw_parse('print("a";)', "should be ',' or ')'", ';')
    compiler.doesnt_raw_parse('let x = (1;)', "should be ')'", ';')
    compiler.doesnt_raw_parse('print(x."wat")', "invalid attribute", '"wat"')


def test_adjacent_expression_parts(compiler):
    compiler.doesnt_raw_parse('print(a b)', "invalid syntax", 'a b')


def test_let_errors(compiler):
    compiler.doesnt_raw_parse('let "wat" = "wut"',
                              "invalid variable name", '"wat"')
    compiler.doesnt_raw_parse('let wat + "wut"',
                              "should be '='", '+')
    compiler.doesnt_raw_parse('export if', "should be 'let'", 'if')


def test_import_errors(compiler):
    compiler.doesnt_raw_parse('import x as y', "should be a string", 'x')
    compiler.doesnt_raw_parse('import "x" if y', "should be 'as'", 'if')
    compiler.doesnt_raw_parse('import "x" as if',
                              "should be a valid module identifier name", 'if')


def test_for_semicolon_error(compiler):
    compiler.doesnt_raw_parse('for let x = 1 else', "should be ';'", 'else')


def test_1line_statement_newline_thingy(compiler):
    compiler.doesnt_raw_parse(
        'print("hi") else', "should be a newline", 'else')


def test_if_elif_else(compiler):
    def calling_body(varname):
        return [FuncCall(Any(), GetVar(Any(), None, varname, None), [])]

    for elifs in [[], ['a'], ['a', 'b']]:
        for got_else in [True, False]:
            code = (
                'if x:\n    xx()\n'
                + ''.join('elif %s:\n    %s%s()\n' % (e, e, e) for e in elifs)
                + int(got_else) * 'else:\n    wat()'
            )

            ifs = [(GetVar(Any(), None, 'x', None), calling_body('xx'))]
            for e in elifs:
                ifs.append((GetVar(Any(), None, e, None), calling_body(e+e)))

            els3 = calling_body('wat') if got_else else []

            assert compiler.raw_parse(code) == [IfStatement(
                location=Any(),
                ifs=ifs,
                else_body=els3
            )]


def test_missing_colon(compiler):
    compiler.doesnt_raw_parse('if a import', "should be ':'", 'import')
