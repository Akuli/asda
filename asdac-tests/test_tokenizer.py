import functools

import pytest

from asdac.common import CompileError, Location
from asdac.tokenizer import Token
from asdac.tokenizer import tokenize as real_tokenize

location = functools.partial(Location, 'test file')


def tokenize(code):
    return list(real_tokenize('test file', code))


def doesnt_tokenize(code, message, bad_code):
    if bad_code is None:
        bad_code = code

    with pytest.raises(CompileError) as error:
        tokenize(code)

    index = code.rindex(bad_code)
    assert error.value.message == message
    assert error.value.location == location(index, len(bad_code))


def test_automatic_trailing_newline():
    assert tokenize('let x = y') == tokenize('let x = y\n')


def test_keyword_in_id():
    assert tokenize('func funcy ffunc func') == [
        Token('keyword', 'func', location(0, 4)),
        Token('id', 'funcy', location(5, 5)),
        Token('id', 'ffunc', location(11, 5)),
        Token('keyword', 'func', location(17, 4)),
        Token('newline', '\n', location(21, 1)),
    ]


def test_indent():
    assert tokenize('if x:\n  y') == [
        Token('keyword', 'if', location(0, 2)),
        Token('id', 'x', location(3, 1)),
        Token('indent', '  ', location(6, 2)),
        Token('id', 'y', location(8, 1)),
        Token('newline', '\n', location(9, 1)),
        Token('dedent', '', location(10, 0)),
    ]

    doesnt_tokenize('if x:\n     y\n z',
                    "the indentation is wrong",
                    ' ')

    assert tokenize('a:\n  b\nx:\n    y') == [
        Token('id', 'a', location(0, 1)),
        Token('indent', '  ', location(3, 2)),
        Token('id', 'b', location(5, 1)),
        Token('newline', '\n', location(6, 1)),
        Token('dedent', '', location(7, 0)),
        Token('id', 'x', location(7, 1)),
        Token('indent', '    ', location(10, 4)),
        Token('id', 'y', location(14, 1)),
        Token('newline', '\n', location(15, 1)),
        Token('dedent', '', location(16, 0)),
    ]

    doesnt_tokenize('x\n y',
                    "indent without : and newline",
                    ' ')
    doesnt_tokenize('x:y',
                    ": without newline and indent",
                    ':')


def test_tabs_forbidden_sorry():
    doesnt_tokenize('print(\t"lol")',
                    "tabs are not allowed in asda code",
                    '\t')
    doesnt_tokenize('print("\t")',
                    "tabs are not allowed in asda code",
                    '\t')

    # tokenizer.py handles tab on first line as a special case, so this is
    # needed for better coverage
    doesnt_tokenize('print("Boo")\nprint("\t")',
                    "tabs are not allowed in asda code",
                    '\t')

    # this should work, because it's backslash t, not an actual tab character
    # note r in front of the python string
    tokenize(r'print("\t")')


def test_strings():
    # string literals can contain \" and \\ just like in python
    string1, string2, string3, fake_newline = tokenize(
        r'"\"" "a \"lol\" b" "\\ back \\ slashes \\"')
    assert string1.value == r'"\""'
    assert string2.value == r'"a \"lol\" b"'
    assert string3.value == r'"\\ back \\ slashes \\"'

    doesnt_tokenize(r'print("hello world\")', "invalid string",
                    r'"hello world\")')
    doesnt_tokenize('"{hello"', "invalid string", None)
    doesnt_tokenize('"{{hello}"', "invalid string", None)
    doesnt_tokenize('"hello}"', "invalid string", None)
    doesnt_tokenize('"{hello}}"', "invalid string", None)
    doesnt_tokenize(r'"\a"', "invalid string", None)


def test_unknown_character():
    doesnt_tokenize('@', "unexpected '@'", '@')


def test_whitespace_ignoring(monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert (tokenize('func lol ( Generator [ Str ] asd ) : \n    boo') ==
            tokenize('func lol(Generator[Str]asd):\n    boo'))
