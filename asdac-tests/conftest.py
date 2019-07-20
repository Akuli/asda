import collections
import pathlib
import types

import pytest

from asdac import (common, tokenizer, string_parser, raw_ast, cooked_ast,
                   opcoder, bytecoder)


# the following url is on 2 lines because pep8 line length
#
# https://docs.pytest.org/en/latest/example/simple.html#control-skipping-of-tes
# ts-according-to-command-line-option
def pytest_addoption(parser):
    parser.addoption(
        "--skipslow", action="store_true", default=False, help="run slow tests"
    )


def pytest_collection_modifyitems(config, items):
    if config.getoption('--skipslow'):
        marker = pytest.mark.skip(reason='--skipslow was used')
        for item in items:
            if 'slow' in item.keywords:
                item.add_marker(marker)


@pytest.fixture
def compiler():
    compilation = None

    def new_compilation():
        nonlocal compilation
        compilation = common.Compilation(
            pathlib.Path('test file'), pathlib.Path('.'), common.Messager(-1))

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

    def cooked_parse(code, want_export_types=False):
        new_compilation()
        raw_statements, imports = raw_ast.parse(compilation, code)

        import_compilations = {}
        for path in imports:
            import_compilations[path] = common.Compilation(
                pathlib.Path(path), pathlib.Path('.'), compilation.messager)
            import_compilations[path].set_imports([])
            import_compilations[path].set_export_types(
                collections.OrderedDict())
        compilation.set_imports(list(import_compilations.values()))

        cooked, export_vars, export_types = cooked_ast.cook(
            compilation, raw_statements, import_compilations)
        assert isinstance(cooked, list)

        if want_export_types:
            return (cooked, export_types)

        assert not export_types
        return cooked

    def opcode(code):
        cooked = cooked_parse(code)     # changes compilation
        compilation.set_export_types(collections.OrderedDict())
        return opcoder.create_opcode(compilation, cooked,
                                     collections.OrderedDict(), code)

    def bytecode(code):
        opcodee = opcode(code)      # changes compilation
        return bytecoder.create_bytecode(compilation, opcodee)

    def doesnt(func):
        def doesnt_func(code, message, bad_code, *, rindex=True):
            if bad_code is None:
                bad_code = code

            with pytest.raises(common.CompileError) as error:
                func(code)

            assert error.value.message == message
            assert error.value.location.offset == (
                code.rindex if rindex else code.index
            )(bad_code)
            assert error.value.location.length == len(bad_code)

        return doesnt_func

    result = types.SimpleNamespace(STRING_PARSE_OFFSET=123)
    for name, value in locals().copy().items():    # magic ftw
        if callable(value) and not name.startswith('_'):
            setattr(result, name, value)
            setattr(result, 'doesnt_' + name, doesnt(value))

    return result
