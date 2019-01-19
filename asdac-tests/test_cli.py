import io
import itertools
import os
import re
import sys

import colorama
import pytest

import asdac.__main__


@pytest.fixture
def asdac_run(monkeypatch, tmp_path):
    paths = (os.path.join(str(tmp_path), str(i)) for i in itertools.count())

    def run(code, opts=(), exit_code=0):
        path = next(paths)
        with open(path, 'w') as file:
            file.write(code)

        monkeypatch.setattr(
            sys, 'argv',
            ['asdac', path, '-o', os.devnull] + list(opts))

        try:
            asdac.__main__.main()
            code = 0
        except SystemExit as e:
            code = 0 if e.code is None else e.code
        assert code == exit_code

    return run


# this seems to be needed for colorama, passing --color=always to asdac is not
# enough to get colors in the output
class FakeTtyStringIO(io.StringIO):
    def isatty(self):
        return True


def red(string):
    return colorama.Fore.RED + string + colorama.Fore.RESET


def test_error_simple(asdac_run, monkeypatch):
    # this doesn't use capsys because it fucks up colorama color codes somehow
    monkeypatch.setattr(sys, 'stderr', FakeTtyStringIO())

    # FIXME: this fails without \n at end of the code
    asdac_run('let asd = lol\n', exit_code=1)

    assert colorama.Fore.RED in sys.stderr.getvalue()

    match = re.fullmatch((
        r'Compiling: .* --> .*\n'
        r'error in .*:1,10...1,13: variable not found: lol\n'
        r'\n'
        r'    (.*)\n'
    ), sys.stderr.getvalue())
    assert match is not None, sys.stderr.getvalue()
    assert match.group(1) == 'let asd = ' + red('lol')


MARKER = '\N{lower one quarter block}'


def test_error_whitespace(asdac_run, monkeypatch):
    monkeypatch.setattr(sys, 'stderr', FakeTtyStringIO())
    asdac_run('a\t\n', exit_code=1)
    assert sys.stderr.getvalue().endswith('\n    a' + red(MARKER * 4) + '\n')


def test_o_needed_stdin(asdac_run, monkeypatch, capsys):
    monkeypatch.setattr(sys, 'argv', ['asdac', '-'])
    with pytest.raises(SystemExit) as error:
        asdac.__main__.main()

    assert error.value.code == 2
    output, errors = capsys.readouterr()
    assert not output
    assert errors.endswith(
        'the -o option is needed when reading source from stdin\n')
