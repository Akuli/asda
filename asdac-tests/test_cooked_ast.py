from asdac import cooked_ast, objects
from asdac.common import Location


def test_reusing_names(compiler):
    compiler.doesnt_cooked_parse(
        'let x = "a"\nfunc lol(Str x) -> void:\n    print("Boo")',
        "there's already a 'x' variable", 'x')
    compiler.doesnt_cooked_parse(
        'let next = "lol"',
        "there's already a generic 'next' function", 'let next = "lol"')
    compiler.doesnt_cooked_parse(
        'let Str = "lol"',
        "'Str' is not a valid variable name because it's a type name",
        'let Str = "lol"')


def test_function_calling_errors(compiler):
    compiler.doesnt_cooked_parse(
        'let x = "lol"\nx("boo")', "expected a function, got Str", 'x')
    compiler.doesnt_cooked_parse(
        'print("a", "b")',
        "cannot call print(Str) with arguments of types: Str, Str",
        '("a", "b")')
    compiler.doesnt_cooked_parse(
        'print()', "cannot call print(Str) with no arguments", '()')


def test_nested_generic_types(compiler):
    [createlocalvar] = compiler.cooked_parse(
        'func lol() -> Generator[Generator[Str]]:\n    print("Lol")')
    assert createlocalvar.varname == 'lol'
    assert createlocalvar.initial_value.type == objects.FunctionType(
        'whatever',
        returntype=objects.GeneratorType(objects.GeneratorType(
            objects.BUILTIN_TYPES['Str'])))


def test_generic_func_not_found(compiler):
    compiler.doesnt_cooked_parse(
        'lol[Str]("hey")', "generic function not found: lol", 'lol[Str]')


def test_missing_attribute(compiler):
    compiler.doesnt_cooked_parse(
        'let x = "hello".boobs', "Str objects have no 'boobs' attribute", '.')


def test_void_function_wrong_call(compiler):
    compiler.doesnt_cooked_parse(
        'let x = print("boo")', "print(Str) doesn't return a value", '("boo")')


def test_unknown_types(compiler):
    compiler.doesnt_cooked_parse('func lol(Wat x) -> void:\n    blah()',
                                 "unknown type 'Wat'", 'Wat')
    compiler.doesnt_cooked_parse('func lol(Wut[Str] x) -> void:\n    blah()',
                                 "unknown generic type 'Wut'", 'Wut[Str]')


def test_assign_errors(compiler):
    compiler.doesnt_cooked_parse(
        'print = "lol"',
        "'print' is of type print(Str), can't assign Str to it",
        'print = "lol"')
    compiler.doesnt_cooked_parse(
        'lol = "woot"', "variable not found: lol", 'lol = "woot"')

    # next is a generic function, not a variable, that's why variable not found
    # TODO: should the error message be more descriptive?
    compiler.doesnt_cooked_parse(
        'next = "woot"', "variable not found: next", 'next = "woot"')


def test_return_errors(compiler):
    # a runtime error is created if a non-void function doesn't return
    for suffix in [' "lol"', '']:
        compiler.doesnt_cooked_parse('return' + suffix,
                                     "return outside function", 'return')

    compiler.doesnt_cooked_parse('func lol() -> void:\n    return "blah"',
                                 "cannot return a value from a void function",
                                 '"blah"')
    compiler.doesnt_cooked_parse('func lol() -> Str:\n    return',
                                 "missing return value", 'return')
    compiler.doesnt_cooked_parse('func lol() -> Str:\n    return print',
                                 "should return Str, not print(Str)", 'print')


def test_yield_errors(compiler):
    compiler.doesnt_cooked_parse(
        'yield "lol"', "yield outside function", 'yield')
    compiler.doesnt_cooked_parse(
        'func lol() -> Generator[Str]:\n    yield print',
        "should yield Str, not print(Str)", 'print')

    for returntype in ['void', 'Str']:
        compiler.doesnt_cooked_parse(
            'func lol() -> %s:\n    yield "hi"' % returntype,
            ("cannot yield in a function that doesn't return "
             "Generator[something]"), 'yield')

    compiler.doesnt_cooked_parse(
        'func lol() -> Generator[Str]:\n    yield "lol"\n    return "Boo"',
        "cannot return a value from a function that yields", 'return')


def test_operator_errors(compiler):
    # the '/' doesn't even tokenize
    compiler.doesnt_cooked_parse('let x = 1 / 2', "unexpected '/'", '/')
    compiler.doesnt_cooked_parse(
        'let x = -"blah"', "expected -Int, got -Str", '-"blah"')
    compiler.doesnt_cooked_parse(
        'let x = 1 - "blah"', "expected Int - Int, got Int - Str", '"blah"')
    compiler.doesnt_cooked_parse(
        'let x = "blah" - 1', "expected Int - Int, got Str - Int", '"blah"')


def test_assign_asd_to_asd(compiler):
    compiler.doesnt_cooked_parse(
        'let asd = asd', "variable not found: asd", 'asd')
    compiler.doesnt_cooked_parse(
        'let asd = "hey"\nlet asd = asd',
        "there's already a 'asd' variable", 'let asd = asd')

    # this one is fine, 'asd = asd' simply does nothing
    assert len(compiler.cooked_parse('let asd = "key"\nasd = asd')) == 2


def test_yield_finding_bugs(compiler):
    compiler.doesnt_cooked_parse(
        'func lol() -> void:\n  for yield x; y; z():\n    xyz()',
        "cannot yield in a function that doesn't return Generator[something]",
        'yield')

    # the yield is in a nested function, should work!
    compiler.cooked_parse('''
func f() -> void:
    func g() -> Generator[Str]:
        yield "Lol"
''')


# not all Generator[Str] functions yield, it's also allowed to return
# a generator
def test_different_generator_creating_functions(compiler):
    create_lol, create_lol2 = compiler.cooked_parse('''
func lol() -> Generator[Str]:
    yield "Hi"
    yield "There"

func lol2() -> Generator[Str]:
    return lol()
''')

    assert create_lol.initial_value.type == create_lol2.initial_value.type


def test_non_bool_cond(compiler):
    first_lines = [
        'if "lol":',
        'while "lol":',
        'for let x = "wat"; "lol"; x = "boo":',
    ]
    for first_line in first_lines:
        compiler.doesnt_cooked_parse('%s\n    print("boo")' % first_line,
                                     "expected Bool, got Str", '"lol"')


def test_joined_string_location_corner_case(compiler):
    let, print_ = compiler.cooked_parse('let x = 1\nprint("hello {x}")')
    [join] = print_.args
    assert join.location.offset == len('let x = 1\nprint(')
    assert join.location.length == len('"hello {x}"')


def test_string_formatting_with_bad_type(compiler):
    compiler.doesnt_cooked_parse(
        'print("{TRUE}")', "Bool objects have no 'to_string' attribute",
        'TRUE')


def test_void_statement(monkeypatch, compiler):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    code = '''
if TRUE:
    print("a")
    %s
    print("b")
'''
    assert (compiler.cooked_parse(code % 'void') ==
            compiler.cooked_parse(code % ''))
    assert (compiler.cooked_parse('for void; TRUE; void:\n    print("Hi")') ==
            compiler.cooked_parse('while TRUE:\n    print("Hi")'))


def test_exporting(compiler):
    cooked, exports = compiler.cooked_parse('let x = 1\nexport let y = 2',
                                            want_exports=True)
    assert exports == {'y': objects.BUILTIN_TYPES['Int']}
    x_create, y_create = cooked
    assert isinstance(x_create, cooked_ast.CreateLocalVar)
    assert isinstance(y_create, cooked_ast.SetVar)


def test_exporting_generic_func(compiler):
    compiler.doesnt_cooked_parse(
        'export func lol[T]() -> void:\n    void',
        "sorry, generic functions can't be exported yet :(", 'func')


def test_import_export_funny_places(compiler):
    compiler.cooked_parse(
        'func lol() -> void:\n    import "lel.asda" as lel')
    compiler.doesnt_cooked_parse(
        'func lol() -> void:\n    export let wut = "woot"',
        "export cannot be used in a function", 'let wut = "woot"')
