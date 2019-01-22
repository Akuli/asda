import pytest

from asdac import tokenizer, raw_ast, cooked_ast
from asdac.common import CompileError, Location


def parse(code):
    return list(cooked_ast.cook(raw_ast.parse(tokenizer.tokenize(
        'test file', code))))


def doesnt_parse(code, message, bad_code):
    with pytest.raises(CompileError) as error:
        parse(code)

    i = code.rindex(bad_code)
    lineno = code[:i].count('\n') + 1
    startcolumn = len(code[:i].split('\n')[-1])
    endcolumn = startcolumn + len(bad_code)

    assert error.value.message == message
    assert error.value.location == Location(
        'test file', lineno, startcolumn, lineno, endcolumn)


def test_generic_lookup_errors():
    doesnt_parse('next[Str, Int]()',
                 "next[T] expected 1 type, but got 2",
                 'next[Str, Int]')
    doesnt_parse('func lol() -> Generator[Str, Int]:\n    print("Boo")',
                 "Generator[T] expected 1 type, but got 2",
                 'Generator[Str, Int]')

    doesnt_parse('''
func lol[T, U](T arg) -> Str:
    return "Hello"

lol[Bool](TRUE)
''', "lol[T, U] expected 2 types, but got 1", 'lol[Bool]')
