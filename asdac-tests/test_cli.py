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


here = os.path.dirname(os.path.abspath(__file__))


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
        (r"(.*): Compiling\.\.\.\n"
         r"error in \1:1,0...1,1: unexpected character U\+FEFF\n[\S\s]*"),
        errors) is not None


def touch(path):
    time.sleep(0.05)    # sometimes fails without this
    os.utime(path, None)


@pytest.fixture
def main_and_lib(tmp_path):
    os.chdir(str(tmp_path))
    with open('main.asda', 'w', encoding='utf-8') as file:
        file.write('import "lib.asda" as lib\nprint(lib.message)')
    with open('lib.asda', 'w', encoding='utf-8') as file:
        file.write('export let message = "Hello"')


# TODO: add an --always-recompile option and test it here
def test_not_recompiling_when_not_needed(main_and_lib, asdac_compile_file):
    run = functools.partial(asdac_compile_file, 'main.asda')
    nothing_done = ("Nothing was compiled because the source files haven't "
                    "changed since the previous compilation.\n")

    assert run() == "main.asda: Compiling...\nlib.asda: Compiling...\n"
    assert run() == nothing_done
    assert run() == nothing_done

    touch('main.asda')
    assert run() == "main.asda: Compiling...\n"
    assert run() == nothing_done

    touch('lib.asda')
    assert run() == "lib.asda: Compiling...\nmain.asda: Compiling...\n"
    assert run() == nothing_done

    touch('main.asda')
    touch('lib.asda')
    assert run() == "main.asda: Compiling...\nlib.asda: Compiling...\n"
    assert run() == nothing_done


# tests verbosities and messages
def test_asdac_session_txt(main_and_lib, asdac_compile_file):
    with open(os.path.join(here, 'asdac-session.txt'),
              encoding='utf-8') as file:
        session = file.read()

    for command, output in re.findall(r'^\$ (.*)\n([^\$]*)', session,
                                      flags=re.MULTILINE):
        print(command, file=sys.__stderr__)
        program, *args = command.split()
        expected_output = output.rstrip()
        if expected_output:
            expected_output += '\n'

        if program == 'touch':
            touch(*args)
            actual_output = ''
        elif program == 'asdac':
            actual_output = asdac_compile_file(*args)
        else:
            assert False, command
        assert expected_output == actual_output, command
