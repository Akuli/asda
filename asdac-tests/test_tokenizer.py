import pytest

from asdac.common import CompileError, Location
from asdac.tokenizer import Token
from asdac.tokenizer import tokenize as real_tokenize


def tokenize(code):
    return list(real_tokenize('test file', code))


def doesnt_tokenize(code, message, bad_code):
    with pytest.raises(CompileError) as error:
        tokenize(code)

    i = code.rindex(bad_code)
    lineno = code[:i].count('\n') + 1
    startcolumn = len(code[:i].split('\n')[-1])
    endcolumn = startcolumn + len(bad_code)

    assert error.value.message == message
    assert error.value.location == Location(
        'test file', lineno, startcolumn, lineno, endcolumn)


def location(startline, startcolumn, endline, endcolumn):
    return Location('test file', startline, startcolumn, endline, endcolumn)


def test_automatic_trailing_newline():
    assert tokenize('let x = y') == tokenize('let x = y\n')


def test_keyword_in_id():
    assert tokenize('func funcy ffunc func') == [
        Token('keyword', 'func', location(1, 0, 1, 4)),
        Token('id', 'funcy', location(1, 5, 1, 10)),
        Token('id', 'ffunc', location(1, 11, 1, 16)),
        Token('keyword', 'func', location(1, 17, 1, 21)),
        Token('newline', '\n', location(1, 21, 2, 0)),
    ]


def test_indent():
    assert tokenize('if x:\n  y') == [
        Token('keyword', 'if', location(1, 0, 1, 2)),
        Token('id', 'x', location(1, 3, 1, 4)),
        Token('indent', '  ', location(2, 0, 2, 2)),
        Token('id', 'y', location(2, 2, 2, 3)),
        Token('newline', '\n', location(2, 3, 3, 0)),
        Token('dedent', '', location(3, 0, 3, 0)),
    ]

    doesnt_tokenize('if x:\n     y\n z',
                    "the indentation is wrong",
                    ' ')

    assert tokenize('a:\n  b\nx:\n    y') == [
        Token('id', 'a', location(1, 0, 1, 1)),
        Token('indent', '  ', location(2, 0, 2, 2)),
        Token('id', 'b', location(2, 2, 2, 3)),
        Token('newline', '\n', location(2, 3, 3, 0)),
        Token('dedent', '', location(3, 0, 3, 0)),
        Token('id', 'x', location(3, 0, 3, 1)),
        Token('indent', '    ', location(4, 0, 4, 4)),
        Token('id', 'y', location(4, 4, 4, 5)),
        Token('newline', '\n', location(4, 5, 5, 0)),
        Token('dedent', '', location(5, 0, 5, 0)),
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
    # the tokenizer doesn't detect which escapes are valid, so \ö tokenizes but
    # fails in raw_ast.py
    string, fake_newline = tokenize(r'"\ö"')
    assert string.value == r'"\ö"'

    # string literals can contain \" and \\ just like in python
    string1, string2, string3, fake_newline = tokenize(
        r'"\"" "a \"lol\" b" "\\ back \\ slashes \\"')
    assert string1.value == r'"\""'
    assert string2.value == r'"a \"lol\" b"'
    assert string3.value == r'"\\ back \\ slashes \\"'

    # never-ending strings should fail with a good error message
    doesnt_tokenize(r'print("hello world\")',
                    "this string never ends",
                    r'"hello world\")')


def test_unknown_character():
    doesnt_tokenize('@', "unexpected '@'", '@')


def test_whitespace_ignoring(monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    assert (tokenize('func lol ( Generator [ Str ] asd ) : \n    boo') ==
            tokenize('func lol(Generator[Str]asd):\n    boo'))
