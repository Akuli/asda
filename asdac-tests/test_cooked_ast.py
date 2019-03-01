import pytest

from asdac import raw_ast, cooked_ast, objects
from asdac.common import Compilation, CompileError, Location


def parse(code, want_exports=False):
    compilation = Compilation('test source', '.')
    raw_statements, imports = raw_ast.parse(compilation, code)
    assert not imports
    cooked, exports = cooked_ast.cook(compilation, raw_statements, {})
    assert isinstance(cooked, list)

    if want_exports:
        return (cooked, exports)

    assert not exports
    return cooked


def doesnt_parse(code, message, bad_code):
    with pytest.raises(CompileError) as error:
        parse(code)

    index = code.rindex(bad_code)
    assert error.value.message == message
    assert error.value.location.offset == index
    assert error.value.location.length == len(bad_code)


def test_reusing_names():
    doesnt_parse('let x = "a"\nfunc lol(Str x) -> void:\n    print("Boo")',
                 "there's already a 'x' variable",
                 'x')
    doesnt_parse('let next = "lol"',
                 "there's already a generic 'next' function",
                 'let next = "lol"')
    doesnt_parse('let Str = "lol"',
                 "'Str' is not a valid variable name because it's a type name",
                 'let Str = "lol"')


def test_function_calling_errors():
    doesnt_parse('let x = "lol"\nx("boo")',
                 "expected a function, got Str",
                 'x')
    doesnt_parse('print("a", "b")',
                 "cannot call print(Str) with arguments of types: Str, Str",
                 '("a", "b")')
    doesnt_parse('print()',
                 "cannot call print(Str) with no arguments",
                 '()')


def test_nested_generic_types():
    [createlocalvar] = parse(
        'func lol() -> Generator[Generator[Str]]:\n    print("Lol")')
    assert createlocalvar.varname == 'lol'
    assert createlocalvar.initial_value.type == objects.FunctionType(
        'whatever',
        returntype=objects.GeneratorType(objects.GeneratorType(
            objects.BUILTIN_TYPES['Str'])))


def test_generic_func_not_found():
    doesnt_parse('lol[Str]("hey")',
                 "generic function not found: lol",
                 'lol[Str]')


def test_missing_attribute():
    doesnt_parse('"hello".boobs()',
                 "Str objects have no 'boobs' method",
                 '.')


def test_void_function_wrong_call():
    doesnt_parse('let x = print("boo")',
                 "print(Str) doesn't return a value",
                 '("boo")')


def test_unknown_types():
    doesnt_parse('func lol(Wat x) -> void:\n    blah()',
                 "unknown type 'Wat'",
                 'Wat')

    doesnt_parse('func lol(Wut[Str] x) -> void:\n    blah()',
                 "unknown generic type 'Wut'",
                 'Wut[Str]')


def test_assign_errors():
    doesnt_parse('print = "lol"',
                 "'print' is of type print(Str), can't assign Str to it",
                 'print = "lol"')
    doesnt_parse('lol = "woot"',
                 "variable not found: lol",
                 'lol = "woot"')

    # next is a generic function, not a variable, that's why variable not found
    # TODO: should the error message be more descriptive?
    doesnt_parse('next = "woot"',
                 "variable not found: next",
                 'next = "woot"')


def test_return_errors():
    # a runtime error is created if a non-void function doesn't return
    for suffix in [' "lol"', '']:
        doesnt_parse('return' + suffix,
                     "return outside function",
                     'return')

    doesnt_parse('func lol() -> void:\n    return "blah"',
                 "cannot return a value from a void function",
                 '"blah"')
    doesnt_parse('func lol() -> Str:\n    return',
                 "missing return value",
                 'return')
    doesnt_parse('func lol() -> Str:\n    return print',
                 "should return Str, not print(Str)",
                 'print')


def test_yield_errors():
    doesnt_parse('yield "lol"',
                 "yield outside function",
                 'yield')
    doesnt_parse('func lol() -> Generator[Str]:\n    yield print',
                 "should yield Str, not print(Str)",
                 'print')

    for returntype in ['void', 'Str']:
        doesnt_parse('func lol() -> %s:\n    yield "hi"' % returntype,
                     ("cannot yield in a function that doesn't return "
                      "Generator[something]"),
                     'yield')

    doesnt_parse(
        'func lol() -> Generator[Str]:\n    yield "lol"\n    return "Boo"',
        "cannot return a value from a function that yields",
        'return')


def test_operator_errors():
    doesnt_parse('let x = 1 / 2',
                 "unexpected '/'",      # actually it doesn't even tokenize
                 '/')
    doesnt_parse('let x = -"blah"',
                 "expected -Int, got -Str",
                 '-"blah"')
    doesnt_parse('let x = 1 - "blah"',
                 "expected Int - Int, got Int - Str",
                 '"blah"')
    doesnt_parse('let x = "blah" - 1',
                 "expected Int - Int, got Str - Int",
                 '"blah"')


def test_assign_asd_to_asd():
    doesnt_parse('let asd = asd',
                 "variable not found: asd",
                 'asd')
    doesnt_parse('let asd = "hey"\nlet asd = asd',
                 "there's already a 'asd' variable",
                 'let asd = asd')

    # this one is fine, 'asd = asd' simply does nothing
    assert len(parse('let asd = "key"\nasd = asd')) == 2


def test_yield_finding_bugs():
    doesnt_parse('func lol() -> void:\n  for yield x; y; z():\n    xyz()',
                 ("cannot yield in a function that doesn't return "
                  "Generator[something]"),
                 'yield')

    # the yield is in a nested function, should work!
    parse('''
func f() -> void:
    func g() -> Generator[Str]:
        yield "Lol"
''')


# not all Generator[Str] functions yield, it's also allowed to return
# a generator
def test_different_generator_creating_functions():
    create_lol, create_lol2 = parse('''
func lol() -> Generator[Str]:
    yield "Hi"
    yield "There"

func lol2() -> Generator[Str]:
    return lol()
''')

    assert (create_lol.initial_value.type ==
            create_lol2.initial_value.type)


def test_non_bool_cond():
    first_lines = [
        'if "lol":',
        'while "lol":',
        'for let x = "wat"; "lol"; x = "boo":',
    ]
    for first_line in first_lines:
        doesnt_parse('%s\n    print("boo")' % first_line,
                     "expected Bool, got Str",
                     '"lol"')


def test_joined_string_location_corner_case():
    let, print_ = parse('let x = 1\nprint("hello {x}")')
    [join] = print_.args
    assert join.location.offset == len('let x = 1\nprint(')
    assert join.location.length == len('"hello {x}"')


def test_string_formatting_with_bad_type():
    doesnt_parse('print("{TRUE}")',
                 "Bool objects have no 'to_string' method",
                 'TRUE')


def test_void_statement(monkeypatch):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))

    code = '''
if TRUE:
    print("a")
    %s
    print("b")
'''
    assert parse(code % 'void') == parse(code % '')
    assert (parse('for void; TRUE; void:\n    print("Hi")') ==
            parse('while TRUE:\n    print("Hi")'))


def test_exporting():
    cooked, exports = parse('let x = 1\nexport let y = 2', want_exports=True)
    assert exports == {'y': objects.BUILTIN_TYPES['Int']}
    x_create, y_create = cooked
    assert isinstance(x_create, cooked_ast.CreateLocalVar)
    assert isinstance(y_create, cooked_ast.SetVar)
