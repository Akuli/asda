import os
import pathlib
import subprocess
import sys

import pytest

from asdac import cooked_ast, objects
from asdac.common import Location


class Any:
    def __eq__(self, other):
        return True


def test_reusing_names(compiler):
    compiler.doesnt_cooked_parse(
        'let x = "a"\nlet lol = (Str x) -> void:\n    void',
        "there's already a 'x' variable", 'Str x')
    compiler.doesnt_cooked_parse(
        'let next = "lol"',
        "there's already a generic 'next' variable", 'let')
    compiler.doesnt_cooked_parse(
        'let Str = "lol"',
        "there's already a 'Str' type", 'let')


def test_function_calling_errors(compiler):
    compiler.doesnt_cooked_parse(
        'let x = "lol"\nx("boo")', "expected a function, got Str", 'x')

    template = ("cannot call functype{(Str) -> void} with %s, "
                "because one argument of type Str is needed")
    compiler.doesnt_cooked_parse(
        'print("a", "b")', template % "arguments of types (Str, Str)",
        'print("a", "b")')
    compiler.doesnt_cooked_parse(
        'print(123)', template % "one argument of type Int", 'print(123)')
    compiler.doesnt_cooked_parse(
        'print()', template % "no arguments", 'print()')


def test_nested_generic_types(compiler):
    [createlocalvar, setvar] = compiler.cooked_parse(
        'let lol = () -> Array[Array[Str]]:\n    print("Lol")')
    assert createlocalvar.var.name == 'lol'
    assert createlocalvar.var is setvar.var
#    assert setvar.value.type == objects.FunctionType(
#        [],
#        objects.ArrayType(objects.ArrayType(
#            objects.BUILTIN_TYPES['Str'])))


def test_generic_var_not_found(compiler):
    compiler.doesnt_cooked_parse(
        'print(lol[Str])', "generic variable not found: lol", 'lol[Str]')


def test_missing_attribute(compiler):
    compiler.doesnt_cooked_parse(
        'let x = "hello".boobs', "Str objects have no 'boobs' attribute",
        '.boobs')


def test_void_function_wrong_call(compiler):
    compiler.doesnt_cooked_parse(
        'let x = print("boo")',
        "functions of type functype{(Str) -> void} don't return a value",
        'print("boo")')


def test_unknown_types(compiler):
    compiler.doesnt_cooked_parse('let lol = (Wat x) -> void:\n    blah()',
                                 "unknown type 'Wat'", 'Wat')
    compiler.doesnt_cooked_parse('let lol = (Wut[Str] x) -> void:\n    blah()',
                                 "unknown generic type 'Wut'", 'Wut[Str]')


def test_assign_errors(compiler):
    compiler.doesnt_cooked_parse(
        'print = "lol"',
        "'print' is of type functype{(Str) -> void}, can't assign Str to it",
        '=')
    compiler.doesnt_cooked_parse(
        'lol = "woot"', "variable not found: lol", '=')

    # next is a generic function, not a variable, that's why variable not found
    # TODO: should the error message be more descriptive?
    compiler.doesnt_cooked_parse(
        'next = "woot"', "variable not found: next", '=')


def test_return_errors(compiler):
    # a runtime error is created if a non-void function doesn't return
    for suffix in [' "lol"', '']:
        compiler.doesnt_cooked_parse('return' + suffix,
                                     "return outside function", 'return')

    compiler.doesnt_cooked_parse('let lol = () -> void:\n    return "blah"',
                                 "cannot return a value from a void function",
                                 '"blah"')
    compiler.doesnt_cooked_parse('let lol = () -> Str:\n    return',
                                 "missing return value", 'return')
    compiler.doesnt_cooked_parse(
        'let lol = () -> Str:\n    return print',
        "should return Str, not functype{(Str) -> void}", 'print')


def test_operator_errors(compiler):
    # the '/' doesn't even tokenize
    compiler.doesnt_cooked_parse('let x = 1 / 2', "unexpected '/'", '/')
    compiler.doesnt_cooked_parse(
        'let x = -"blah"', "expected -Int, got -Str", '-')
    compiler.doesnt_cooked_parse(
        'let x = 1 - "blah"', "expected Int - Int, got Int - Str", '"blah"')
    compiler.doesnt_cooked_parse(
        'let x = "blah" - 1', "expected Int - Int, got Str - Int", '"blah"')


def test_assign_asd_to_asd(compiler):
    compiler.doesnt_cooked_parse(
        'let asd = asd', "variable not found: asd", 'asd')
    compiler.doesnt_cooked_parse(
        'let asd = "hey"\nlet asd = asd',
        "there's already a 'asd' variable", 'let')

    # this one is fine, 'asd = asd' simply does nothing
    assert len(compiler.cooked_parse('let asd = "key"\nasd = asd')) == 3


def test_non_bool_cond(compiler):
    body = '\n' + ' '*4 + 'print("wat")'
    codes = [
        'if "lol":' + body,
        'while "lol":' + body,
        'for let x = "wat"; "lol"; x = "boo":' + body,
        'print(if "lol" then "a" else "b")',
    ]
    for code in codes:
        compiler.doesnt_cooked_parse(code, "expected Bool, got Str", '"lol"')


def test_for_loop_scoping(compiler):
    compiler.doesnt_cooked_parse(
        ('for let i = 0; i != 10; i = i+1:\n'
         '    void\n'
         'print(i)\n'),
        "variable not found: i", 'i')


def test_if_expression_wrong_types(compiler):
    compiler.doesnt_cooked_parse(
        'print(if TRUE then "a" else 123)',
        "'then' value has type Str, but 'else' value has type Int", 'if')


def test_joined_string_location_corner_case(compiler):
    *let, print_ = compiler.cooked_parse('let x = 1\nprint("hello {x}")')
    [join] = print_.args
    assert join.location.offset == len('let x = 1\nprint(')
    assert join.location.length == len('"hello {x}"')


def test_string_formatting_with_bad_type(compiler):
    compiler.doesnt_cooked_parse(
        'print("{TRUE}")', "Bool objects have no 'to_string' attribute",
        'TRUE')


def test_void_statement(monkeypatch, compiler):
    monkeypatch.setattr(Location, '__eq__', (lambda self, other: True))
    monkeypatch.setattr(cooked_ast.Variable, '__eq__',
                        lambda self, other: (self.name == other.name))
    code = '''
let f = () -> void:
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
                                            want_export_types=True)
    assert exports == {'y': objects.BUILTIN_TYPES['Int']}
    x_create, x_set, y_set = cooked
    assert isinstance(x_create, cooked_ast.CreateLocalVar)
    assert isinstance(x_set, cooked_ast.SetVar)
    assert isinstance(y_set, cooked_ast.SetVar)


def test_exporting_generic_var(compiler):
    with pytest.raises(AssertionError) as error_info:
        compiler.cooked_parse('export let lol[T] = "heh"')

    assert str(error_info.value).startswith("sorry, cannot export generic var")


def test_import_export_funny_places(compiler):
    compiler.doesnt_cooked_parse(
        'let lol= () -> void:\n    import "lel.asda" as lel',
        "cannot import here, only at beginning of file", 'import')
    compiler.doesnt_cooked_parse(
        'let lol = () -> void:\n    export let wut = "woot"',
        # TODO: is it possible to make this point at 'export'?
        "export cannot be used in a function", 'let')


def test_module_name_same_as_var_name(compiler, tmp_path, monkeypatch):
    env = dict(os.environ)
    env.setdefault('PYTHONPATH', '')
    if env['PYTHONPATH']:
        env['PYTHONPATH'] += os.pathsep
    env['PYTHONPATH'] += str(pathlib.Path(__file__).absolute().parent.parent)

    os.chdir(str(tmp_path))
    pathlib.Path('emptiness.asda').touch()
    subprocess.check_call(
        [sys.executable, '-m', 'asdac', 'emptiness.asda'], env=env)
    compiler.cooked_parse('import "emptiness.asda" as lol\nlet lol = 1')


def test_constructor_errors(compiler):
    compiler.doesnt_cooked_parse(
        'let x = new Bool(1, 2, 3)',
        "cannot create Bool objects with 'new Bool(...)'", 'new')
    compiler.doesnt_cooked_parse(
        'let y = new VariableError(1, 2, 3)',
        ("cannot do 'new VariableError(...)' "
         "with arguments of types (Int, Int, Int), "
         "because one argument of type Str is needed"),
        'new')


def test_bad_throw(compiler):
    compiler.doesnt_cooked_parse(
        'throw "lol"', "should be an Error object", '"lol"')


def test_this_assigning_disallowed(compiler):
    compiler.doesnt_cooked_parse('''\
class Foo():
    method lol() -> void:
        this = new Foo()
''', 'invalid assignment', '=')

    compiler.doesnt_cooked_parse(
        'print(this)', "'this' can be used only inside methods", 'this')
