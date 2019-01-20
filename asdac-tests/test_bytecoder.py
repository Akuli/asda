import pytest

from asdac import tokenizer, raw_ast, cooked_ast, opcoder, bytecoder
from asdac.common import CompileError


def bytecode(code):
    return bytecoder.create_bytecode(opcoder.create_opcode(
        cooked_ast.cook(raw_ast.parse(tokenizer.tokenize('test file', code)))))


def test_too_many_arguments():
    args = map('Str s{}'.format, range(0xff + 1))
    code = 'func lol(%s) -> void:\n    print("boo")' % ', '.join(args)
    print(code)

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
