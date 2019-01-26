import pytest

from asdac import tokenizer, raw_ast, cooked_ast, bytecoder
from asdac.common import CompileError
from asdac.opcoder import create_opcode, Return, DidntReturnError


def opcode(code):
    return create_opcode(cooked_ast.cook(raw_ast.parse('test file', code)))


def bytecode(code):
    return bytecoder.create_bytecode(opcode(code))


def test_too_many_arguments():
    args = map('Str s{}'.format, range(0xff + 1))
    code = 'func lol(%s) -> void:\n    print("boo")' % ', '.join(args)

    # the error message doesn't say clearly what actually went wrong because it
    # comes from generic uint writing code, but i think that's fine because who
    # would actually use more than 0xff arguments anyway
    #
    # FIXME: the location being None is bad
    with pytest.raises(CompileError) as error:
        bytecode(code)
    assert error.value.message == (
        "this number does not fit in an unsigned 8-bit integer: %d" % (0xff+1))
    assert error.value.location is None     # FIXME


def test_implicit_return():
    codes = [
        'func lol() -> void:\n    print("Boo")',
        'func lol() -> Generator[Str]:\n    yield "Boo"',
    ]

    for code in codes:
        create_func, setvar = opcode(code).ops
        implicit_return = create_func.body_opcode.ops[-1]
        assert isinstance(implicit_return, Return)
        assert not implicit_return.returns_a_value


def test_missing_return():
    create_func, setvar = opcode('func lol() -> Str:\n    print("Boo")').ops
    didnt_return_error = create_func.body_opcode.ops[-1]
    assert isinstance(didnt_return_error, DidntReturnError)
