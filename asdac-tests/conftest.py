import collections
import types

import pytest

from asdac import (common, tokenizer, string_parser, raw_ast, cooked_ast,
                   opcoder, bytecoder)


@pytest.fixture
def compiler():
    compilation = None

    def new_compilation():
        nonlocal compilation
        compilation = common.Compilation('test file', '.')

    def tokenize(code):
        new_compilation()
        return list(tokenizer.tokenize(compilation, code))

    def string_parse(string):
        new_compilation()
        location = common.Location(compilation, result.STRING_PARSE_OFFSET,
                                   len(string))
        return list(string_parser.parse(string, location))

    def raw_parse(code):
        new_compilation()
        raw_statements, imports = raw_ast.parse(compilation, code)
        assert not imports
        return raw_statements

    def cooked_parse(code, want_exports=False):
        cooked, exports = cooked_ast.cook(compilation, raw_parse(code), {})
        assert isinstance(cooked, list)

        if want_exports:
            return (cooked, exports)

        assert not exports
        return cooked

    def opcode(code):
        cooked = cooked_parse(code)     # changes compilation
        compilation.set_imports([])
        compilation.set_exports(collections.OrderedDict())
        return opcoder.create_opcode(compilation, cooked, code)

    def bytecode(code):
        opcodee = opcode(code)      # changes compilation
        return bytecoder.create_bytecode(compilation, opcodee)

    def doesnt(func):
        def doesnt_func(code, message, bad_code):
            if bad_code is None:
                bad_code = code

            with pytest.raises(common.CompileError) as error:
                func(code)

            assert error.value.message == message
            assert error.value.location.offset == code.rindex(bad_code)
            assert error.value.location.length == len(bad_code)

        return doesnt_func

    result = types.SimpleNamespace(STRING_PARSE_OFFSET=123)
    for name, value in locals().copy().items():    # magic ftw
        if callable(value) and not name.startswith('_'):
            setattr(result, name, value)
            setattr(result, 'doesnt_' + name, doesnt(value))

    return result
