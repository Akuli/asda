import functools
import pathlib

from asdac import common
from asdac.tokenizer import Token


class Any:
    def __eq__(self, other):
        return True


location = functools.partial(common.Location, Any())


def test_automatic_trailing_newline(compiler, monkeypatch):
    monkeypatch.setattr(common.Location, '__eq__', (lambda *shit: True))
    tokens1 = compiler.tokenize('let x = y')
    tokens2 = compiler.tokenize('let x = y\n')
    assert tokens1 == tokens2


def test_keyword_in_id(compiler):
    assert compiler.tokenize('let lett llet let') == [
        Token('KEYWORD', 'let', Any()),
        Token('ID', 'lett', Any()),
        Token('ID', 'llet', Any()),
        Token('KEYWORD', 'let', Any()),
        Token('NEWLINE', Any(), Any()),
    ]


def test_indent(compiler):
    assert compiler.tokenize('if x:\n  y') == [
        Token('KEYWORD', 'if', Any()),
        Token('ID', 'x', Any()),
        Token('INDENT', '  ', Any()),
        Token('ID', 'y', Any()),
        Token('NEWLINE', Any(), Any()),
        Token('DEDENT', '', Any()),
        Token('NEWLINE', Any(), Any()),
    ]

    compiler.doesnt_tokenize('if x:\n     y\n z',
                             "the indentation is wrong", ' ')

    assert compiler.tokenize('a:\n  b\nx:\n    y') == [
        Token('ID', 'a', Any()),
        Token('INDENT', '  ', Any()),
        Token('ID', 'b', Any()),
        Token('NEWLINE', Any(), Any()),
        Token('DEDENT', '', Any()),
        Token('NEWLINE', Any(), Any()),
        Token('ID', 'x', Any()),
        Token('INDENT', '    ', Any()),
        Token('ID', 'y', Any()),
        Token('NEWLINE', Any(), Any()),
        Token('DEDENT', '', Any()),
        Token('NEWLINE', Any(), Any()),
    ]

    compiler.doesnt_tokenize('x\n y', "indent without : and newline", ' ')
    compiler.doesnt_tokenize('x:y', ": without newline and indent", ':')


def test_tabs_forbidden_sorry(compiler):
    compiler.doesnt_tokenize('print(\t"lol")',
                             "tabs are not allowed in asda code", '\t')
    compiler.doesnt_tokenize('print("\t")',
                             "tabs are not allowed in asda code", '\t')

    # tokenizer.py handles tab on first line as a special case, so this is
    # needed for better coverage
    compiler.doesnt_tokenize('print("Boo")\nprint("\t")',
                             "tabs are not allowed in asda code", '\t')

    # this should work, because it's backslash t, not an actual tab character
    # note r in front of the python string
    compiler.tokenize(r'print("\t")')


def test_strings(compiler):
    # string literals can contain \" and \\ just like in python
    string1, string2, string3, fake_newline = compiler.tokenize(
        r'"\"" "a \"lol\" b" "\\ back \\ slashes \\"')
    assert string1.value == r'"\""'
    assert string2.value == r'"a \"lol\" b"'
    assert string3.value == r'"\\ back \\ slashes \\"'

    compiler.doesnt_tokenize(r'print("hello world\")', "invalid string", '"',
                             rindex=False)
    compiler.doesnt_tokenize('"{hello"', "invalid string", '"', rindex=False)
    compiler.doesnt_tokenize('"{{hello}"', "invalid string", '"', rindex=False)
    compiler.doesnt_tokenize('"hello}"', "invalid string", '"', rindex=False)
    compiler.doesnt_tokenize('"{hello}}"', "invalid string", '"', rindex=False)
    compiler.doesnt_tokenize(r'"\a"', "invalid string", '"', rindex=False)


def test_unknown_character(compiler):
    compiler.doesnt_tokenize('@', "unexpected '@'", '@')


def test_whitespace_ignoring(monkeypatch, compiler):
    monkeypatch.setattr(common.Location, '__eq__', (lambda *shit: True))
    assert (compiler.tokenize('func lol ( Generator [ Str ] asd ) : \n    boo')
            == compiler.tokenize('func lol(Generator[Str]asd):\n    boo'))
