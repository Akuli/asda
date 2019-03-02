import codecs
import functools
import io
import itertools
import os
import random
import re
import sys
import time

import colorama
import pytest

import asdac.__main__


@pytest.fixture
def asdac_compile(monkeypatch, tmp_path):
    paths = (os.path.join(str(tmp_path), str(i)) for i in itertools.count())

    def run(code, opts=(), exit_code=0):
        path = next(paths)
        os.mkdir(path)
        os.chdir(path)
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
    def run(file):
        monkeypatch.setattr(sys, 'argv', ['asdac', file])
        asdac.__main__.main()
        output, errors = capsys.readouterr()
        assert not output

        # i don't care about the order, but there must be no duplicates
        lines = errors.replace(os.sep, '/').splitlines()
        assert len(set(lines)) == len(lines), lines
        return set(lines)

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
        r'Compiling: file\.asda --> asda-compiled%sfile\.asdac\n'
        r'error in .*:1,10...1,13: variable not found: lol\n'
        r'\n'
        r'    (.*)\n' % re.escape(os.sep)
    ), sys.stderr.getvalue())
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


def test_cant_read_stdin(asdac_compile, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['asdac', '-'])
    with pytest.raises(SystemExit) as error:
        asdac.__main__.main()

    assert error.value.code == 2
    output, errors = capsys.readouterr()
    assert not output
    assert errors.endswith("reading from stdin is not supported\n")


def test_bom(asdac_compile, capsys):
    bom = codecs.BOM_UTF8.decode('utf-8')

    asdac_compile('print("hello")', exit_code=0)
    asdac_compile(bom + 'print("hello")', exit_code=0)
    output, errors = capsys.readouterr()
    assert not output
    assert errors.count('\n') == 2

    asdac_compile(bom + bom + 'print("hello")', exit_code=1)
    output, errors = capsys.readouterr()
    assert not output
    assert re.fullmatch(
        (r"Compiling: .* --> .*\n"
         r"error in .*: unexpected character U\+FEFF\n[\S\s]*"),
        errors) is not None


def touch(path):
    time.sleep(0.05)    # sometimes fails without this
    os.utime(path, None)


# TODO: add an --always-recompile option and test it here
def test_not_recompiling_when_not_needed(tmp_path, asdac_compile_file):
    os.chdir(str(tmp_path))
    with open('main.asda', 'w', encoding='utf-8') as file:
        file.write('import "lib.asda" as lib\nprint(lib.message)')
    with open('lib.asda', 'w', encoding='utf-8') as file:
        file.write('export let message = "Hello"')

    run = functools.partial(asdac_compile_file, 'main.asda')

    assert run() == {"Compiling: main.asda --> asda-compiled/main.asdac",
                     "Compiling: lib.asda --> asda-compiled/lib.asdac"}
    assert run() == {"No need to recompile main.asda",
                     "No need to recompile lib.asda"}
    assert run() == {"No need to recompile main.asda",
                     "No need to recompile lib.asda"}

    touch('main.asda')
    assert run() == {"Compiling: main.asda --> asda-compiled/main.asdac",
                     "No need to recompile lib.asda"}
    assert run() == {"No need to recompile main.asda",
                     "No need to recompile lib.asda"}

    touch('lib.asda')
    assert run() == {"Compiling: main.asda --> asda-compiled/main.asdac",
                     "Compiling: lib.asda --> asda-compiled/lib.asdac"}
    assert run() == {"No need to recompile main.asda",
                     "No need to recompile lib.asda"}

    touch('main.asda')
    touch('lib.asda')
    assert run() == {"Compiling: main.asda --> asda-compiled/main.asdac",
                     "Compiling: lib.asda --> asda-compiled/lib.asdac"}
    assert run() == {"No need to recompile main.asda",
                     "No need to recompile lib.asda"}
