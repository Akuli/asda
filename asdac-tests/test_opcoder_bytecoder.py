import pytest

from asdac.common import CompileError
from asdac.opcoder import Return, DidntReturnError


@pytest.mark.slow
def test_too_many_arguments(compiler):
    args = list(map('Str s{}'.format, range(0xff + 1)))
    code = 'let omfg = (%s) -> void:\n    print("boo")' % ', '.join(args)

    # the error message doesn't say clearly what actually went wrong because it
    # comes from generic uint writing code, but i think that's fine because who
    # would actually use more than 0xff arguments anyway
    #
    # FIXME: the location being None is bad, opcode and bytecode should include
    # line numbers and filename everywhere
    with pytest.raises(CompileError) as error:
        compiler.bytecode(code)
    assert error.value.message == (
        "this number does not fit in an unsigned 8-bit integer: %d" % (0xff+1))
    assert error.value.location is None     # TODO: this sucks dick

    # 0xff arguments should work, because 0xff fits in an 8-bit uint
    compiler.bytecode(
        'let omfg = (%s) -> void:\n    print("boo")' % ', '.join(args[1:]))


def test_implicit_and_missing_return(compiler):
    [createfunc, setvar] = compiler.opcode(
        'let lol = () -> void:\n    print("Boo")').ops
    implicit_return = createfunc.body_opcode.ops[-1]
    assert isinstance(implicit_return, Return)
    assert not implicit_return.returns_a_value

    create_func, setvar = compiler.opcode(
        'let lol = () -> Str:\n    print("Boo")').ops
    didnt_return_error = create_func.body_opcode.ops[-1]
    assert isinstance(didnt_return_error, DidntReturnError)
