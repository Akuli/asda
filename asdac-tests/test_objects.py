def test_generic_lookup_errors(compiler):
    compiler.doesnt_cooked_parse(
        'next[Str, Int]()', "needs 1 type, but got 2 types: [Str, Int]",
        'next[Str, Int]')
    compiler.doesnt_cooked_parse(
        'let lol = () -> Array[Str, Int]:\n    print("Boo")',
        "needs 1 type, but got 2 types: [Str, Int]", 'Array[Str, Int]')

    compiler.doesnt_cooked_parse('''
let lol[T, U] = (T arg) -> Str:
    return "Hello"

lol[Bool](TRUE)
''', "needs 2 types, but got 1 type: [Bool]", 'lol[Bool]')


# there used to be a bug that couldn't handle genericness in void-returning
# functions
def test_void_returning_generic_bug(compiler):
    lol_create, lol_set, f_create, f_set = compiler.cooked_parse(
        'let lol[T] = () -> void:\n    print("Hello")\nlet f = lol[Str]')
    assert f_set.value.type.returntype is None
