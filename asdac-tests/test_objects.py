def test_generic_lookup_errors(compiler):
    compiler.doesnt_cooked_parse(
        'next[Str, Int]()', "expected 1 type, [T], but got 2",
        'next[Str, Int]')
    compiler.doesnt_cooked_parse(
        'let lol = () -> Generator[Str, Int]:\n    print("Boo")',
        "expected 1 type, [T], but got 2", 'Generator[Str, Int]')

    compiler.doesnt_cooked_parse('''
let lol[T, U] = (T arg) -> Str:
    return "Hello"

lol[Bool](TRUE)
''', "expected 2 types, [T, U], but got 1", 'lol[Bool]')


# there used to be a bug that couldn't handle genericness in void-returning
# functions
def test_void_returning_generic_bug(compiler):
    lol_definition, f_definition = compiler.cooked_parse(
        'let lol[T] = () -> void:\n    print("Hello")\nlet f = lol[Str]')
    assert f_definition.initial_value.type.returntype is None
