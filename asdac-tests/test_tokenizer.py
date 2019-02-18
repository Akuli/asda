import functools

import pytest

from asdac.common import CompileError, Location
from asdac.tokenizer import tokenize as real_tokenize

location = functools.partial(Location, 'test file')


def tokens_equal(a, b, *, consider_index=True):
    if consider_index:
        return (a.type, a.value, a.index) == (b.type, b.value, b.index)
    return (a.type, a.value) == (b.type, b.value)


# for checking == stuff with sly tokens
class Token:

    def __init__(self, *args):
        self.type, self.value, self.index = args

    __eq__ = tokens_equal


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
    tokens1 = tokenize('let x = y')
    tokens2 = tokenize('let x = y\n')
    assert len(tokens1) == len(tokens2)
    assert all(map(tokens_equal, tokens1, tokens2))


def test_keyword_in_id():
    assert tokenize('func funcy ffunc func') == [
        Token('KEYWORD', 'func', 0),
        Token('ID', 'funcy', 5),
        Token('ID', 'ffunc', 11),
        Token('KEYWORD', 'func', 17),
        Token('NEWLINE', '\n', 21),
    ]


def test_indent():
    assert tokenize('if x:\n  y') == [
        Token('KEYWORD', 'if', 0),
        Token('ID', 'x', 3),
        Token('INDENT', '  ', 6),
        Token('ID', 'y', 8),
        Token('NEWLINE', '\n', 9),
        Token('DEDENT', '', 10),
    ]

    doesnt_tokenize('if x:\n     y\n z',
                    "the indentation is wrong",
                    ' ')

    assert tokenize('a:\n  b\nx:\n    y') == [
        Token('ID', 'a', 0),
        Token('INDENT', '  ', 3),
        Token('ID', 'b', 5),
        Token('NEWLINE', '\n', 6),
        Token('DEDENT', '', 7),
        Token('ID', 'x', 7),
        Token('INDENT', '    ', 10),
        Token('ID', 'y', 14),
        Token('NEWLINE', '\n', 15),
        Token('DEDENT', '', 16),
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
    Token = type(tokenize('a')[0])
    monkeypatch.setattr(Token, '__eq__', functools.partialmethod(
        tokens_equal, consider_index=False))

    assert (tokenize('func lol ( Generator [ Str ] asd ) : \n    boo') ==
            tokenize('func lol(Generator[Str]asd):\n    boo'))
