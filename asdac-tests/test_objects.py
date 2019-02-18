import pytest

from asdac import raw_ast, cooked_ast
from asdac.common import CompileError, Location


def parse(code):
    return list(cooked_ast.cook(raw_ast.parse('test file', code)))


def doesnt_parse(code, message, bad_code):
    with pytest.raises(CompileError) as error:
        parse(code)

    index = code.rindex(bad_code)

    assert error.value.message == message
    assert error.value.location == Location('test file', index, len(bad_code))


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


# there used to be a bug that couldn't handle genericness in void-returning
# functions
def test_void_returning_generic_bug():
    ast = parse('func lol[T]() -> void:\n    print("Hello")\nlet f = lol[Str]')
    loldef, fdef = ast
    assert fdef.initial_value.type.returntype is None
