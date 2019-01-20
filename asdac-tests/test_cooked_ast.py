import pytest

from asdac import tokenizer, raw_ast, objects
from asdac.common import CompileError, Location
from asdac.cooked_ast import (cook, CallFunction, CreateFunction,
                              CreateLocalVar, LookupVar, StrConstant,
                              ValueReturn, Yield)


def parse(code):
    return list(cook(raw_ast.parse(tokenizer.tokenize('test file', code))))


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
                 'print("a", "b")')
    doesnt_parse('print()',
                 "cannot call print(Str) with no arguments",
                 'print()')


# lol
class Anything:
    def __eq__(self, other):
        return True


def test_nested_generic_types():
    ast = parse('func lol() -> Generator[Generator[Str]]:\n    print("Lol")')
    assert ast == [
        CreateLocalVar(
            Location('test file', *([Anything()] * 4)),
            type=objects.FunctionType(
                'whatever',
                returntype=objects.GeneratorType(
                    objects.GeneratorType(
                        objects.BUILTIN_TYPES['Str']))),
            varname='lol',
            initial_value=Anything())]


def test_generic_func_not_found():
    doesnt_parse('lol[Str]("hey")',
                 "generic function not found: lol",
                 'lol[Str]')


def test_missing_attribute():
    doesnt_parse('"hello".boobs()',
                 "Str objects have no 'boobs' method",
                 '"hello".boobs')


def test_void_function_wrong_call():
    doesnt_parse('let x = print("boo")',
                 "print(Str) doesn't return a value",
                 'print("boo")')


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
    # TODO: what if a non-void function doesn't return?
    for suffix in [' "lol"', '']:
        doesnt_parse('return' + suffix,
                     "return outside function",
                     'return' + suffix)

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
                 'yield "lol"')
    doesnt_parse('func lol() -> Generator[Str]:\n    yield print',
                 "should yield Str, not print(Str)",
                 'print')

    for returntype in ['void', 'Str']:
        doesnt_parse('func lol() -> %s:\n    yield "hi"' % returntype,
                     ("cannot yield in a function that doesn't return "
                      "Generator[something]"),
                     'yield "hi"')

    doesnt_parse(
        'func lol() -> Generator[Str]:\n    yield "lol"\n    return "Boo"',
        "cannot return a value from a function that yields",
        'return "Boo"')


# not all Generator[Str] functions yield, it's also allowed to return
# a generator
def test_different_generator_creating_functions():
    # the actual value of the ast kinda needs to be checked to make sure that
    # it does the right thing :/
    strgen = objects.GeneratorType(objects.BUILTIN_TYPES['Str'])
    functype = objects.FunctionType('whatever', [], strgen)
    anywhere = Location('test file', *([Anything()] * 4))

    def string(s):
        return StrConstant(anywhere, type=objects.BUILTIN_TYPES['Str'],
                           python_string=s)

    def create_func(name, yields, body):
        return CreateLocalVar(
            anywhere,
            type=functype,
            varname=name,
            initial_value=CreateFunction(
                anywhere,
                type=functype,
                name=name,
                argnames=[],
                body=body,
                yields=yields,
            ),
        )

    assert parse('''
func lol() -> Generator[Str]:
    yield "Hi"
    yield "There"

func lol2() -> Generator[Str]:
    return lol()
''') == [
        create_func('lol', True, [
            Yield(
                anywhere,
                type=None,
                value=string('Hi'),
            ),
            Yield(
                anywhere,
                type=None,
                value=string('There'),
            ),
        ]),
        create_func('lol2', False, [
            ValueReturn(
                anywhere,
                type=None,
                value=CallFunction(
                    anywhere,
                    type=strgen,
                    function=LookupVar(
                        anywhere,
                        type=functype,
                        varname='lol',
                        level=1,
                    ),
                    args=[],
                ),
            ),
        ]),
    ]


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
