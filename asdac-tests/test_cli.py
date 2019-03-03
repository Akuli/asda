# see also test_shell_sessions.txt
import io
import itertools
import os
import pathlib
import random
import re
import sys

import colorama
import pytest

import asdac.__main__


@pytest.fixture
def asdac_compile(monkeypatch, tmp_path):
    paths = (tmp_path / str(i) for i in itertools.count())

    def run(code, opts=(), exit_code=0):
        path = next(paths)
        path.mkdir()
        os.chdir(str(path))
        with open('file.asda', 'w', encoding='utf-8',
                  newline=random.choice(['\n', '\r\n'])) as file:
            file.write(code)

        monkeypatch.setattr(sys, 'argv', ['asdac', 'file.asda'])
        try:
            asdac.__main__.main()
            code = 0
        except SystemExit as e:
            code = 0 if e.code is None else e.code
        assert code == exit_code

    return run


@pytest.fixture
def asdac_compile_file(monkeypatch, capsys):
    def run(file, *extra_options):
        monkeypatch.setattr(sys, 'argv', ['asdac', file] + list(extra_options))
        asdac.__main__.main()
        output, errors = capsys.readouterr()
        assert not output
        return errors.replace(os.sep, '/')

    return run


# this seems to be needed for colorama, passing --color=always to asdac is not
# enough to get colors in the output
class FakeTtyStringIO(io.StringIO):
    def isatty(self):
        return True


def red(string):
    return colorama.Fore.RED + string + colorama.Fore.RESET


def test_error_simple(asdac_compile, monkeypatch):
    # this doesn't use capsys because it fucks up colorama colors somehow
    #                                    ^^^^^  <--- bad word, omg
    monkeypatch.setattr(sys, 'stderr', FakeTtyStringIO())

    asdac_compile('let asd = lol', exit_code=1)
    assert colorama.Fore.RED in sys.stderr.getvalue()

    match = re.fullmatch((
        r'file\.asda: Compiling\.\.\.\n'
        r'error in file\.asda:1,10...1,13: variable not found: lol\n'
        r'\n'
        r'    (.*)\n'), sys.stderr.getvalue())
    assert match is not None, sys.stderr.getvalue()
    assert match.group(1) == 'let asd = ' + red('lol')


MARKER = '\N{lower one quarter block}' * 4


def test_error_whitespace(asdac_compile, monkeypatch):
    monkeypatch.setattr(sys, 'stderr', FakeTtyStringIO())
    asdac_compile('a\t\n', exit_code=1)
    assert sys.stderr.getvalue().endswith('\n    a' + red(MARKER) + '\n')


def test_error_empty_location(asdac_compile, monkeypatch):
    monkeypatch.setattr(sys, 'stderr', FakeTtyStringIO())
    asdac_compile('print("{}")', exit_code=1)
    assert sys.stderr.getvalue().endswith(
        '\n    print("{%s}")\n' % red(MARKER))


def test_invalid_arg_errors(monkeypatch, capsys, tmp_path):
    os.chdir(str(tmp_path))
    os.mkdir('asda-compiled')

    def run(*args):
        monkeypatch.setattr(sys, 'argv', ['asdac'] + list(args))
        with pytest.raises(SystemExit) as error:
            asdac.__main__.main()

        assert error.value.code == 2
        output, errors = capsys.readouterr()
        assert not output
        return errors

    assert run('-').endswith(": reading from stdin is not supported\n")

    lol = pathlib.Path('asda-compiled', 'lol.asda')
    lol.touch()
    assert run(str(lol)).endswith(
        ": refusing to compile '%s' because it is in 'asda-compiled'\n" % lol)
