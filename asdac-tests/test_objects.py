def test_generic_lookup_errors(compiler):
    compiler.doesnt_cooked_parse(
        'next[Str, Int]()', "next[T] expected 1 type, but got 2",
        'next[Str, Int]')
    compiler.doesnt_cooked_parse(
        'func lol() -> Generator[Str, Int]:\n    print("Boo")',
        "Generator[T] expected 1 type, but got 2", 'Generator[Str, Int]')

    compiler.doesnt_cooked_parse('''
func lol[T, U](T arg) -> Str:
    return "Hello"

lol[Bool](TRUE)
''', "lol[T, U] expected 2 types, but got 1", 'lol[Bool]')


# there used to be a bug that couldn't handle genericness in void-returning
# functions
def test_void_returning_generic_bug(compiler):
    lol_definition, f_definition = compiler.cooked_parse(
        'func lol[T]() -> void:\n    print("Hello")\nlet f = lol[Str]')
    assert f_definition.initial_value.type.returntype is None
