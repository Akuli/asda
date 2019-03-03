# pytest file that compiles and runs the examples
import os
import pathlib
import re
import shutil
import subprocess
import sys

import pytest

import asdac.__main__
import pyasda.__main__

examples_dir = pathlib.Path(__file__).absolute().parent.parent / 'examples'


@pytest.fixture
def compiler(tmp_path, monkeypatch, capsys):
    # python has a built-in compile function, so creating my own 'compile'
    # function would be bad style
    # this is even worse style :DD  MUHAHAA
    def compi1e(filename):
        monkeypatch.chdir(tmp_path)
        for other_file in examples_dir.iterdir():
            if other_file.suffix == '.asda':
                shutil.copy(str(other_file), '.')

        monkeypatch.setattr(sys, 'argv', ['asdac', str(filename)])
        asdac.__main__.main()

        out, err = capsys.readouterr()
        assert not out

        assert all(line.endswith(': Compiling...')
                   for line in err.splitlines())
        match = re.search(r'^(.*): Compiling\.\.\.\n', err)
        assert match is not None, repr(err)
        assert match.group(1) == filename
        return 'asda-compiled' + os.sep + match.group(1) + 'c'

    return compi1e


@pytest.fixture
def runner(monkeypatch, capsys):
    def run(filename):
        monkeypatch.setattr(sys, 'argv', ['pyasda', str(filename)])
        pyasda.__main__.main()

        out, err = capsys.readouterr()
        assert not err
        return out

    return run


def create_test_func(filename):
    def test_func(compiler, runner):
        compiled = compiler(filename + '.asda')
        output = runner(compiled)

        output_path = examples_dir / 'output' / (filename + '.txt')
        with output_path.open('r', encoding='utf-8') as file:
            assert output == file.read()

    # magic is fun
    test_func.__name__ = test_func.__qualname__ = 'test_%s_example' % path.stem
    globals()[test_func.__name__] = test_func


for path in (examples_dir / 'output').iterdir():
    if path.suffix == '.txt':
        create_test_func(path.stem)


# can't use the runner that other tests use because running must be interrupted
def test_while_example(compiler):
    compiled = compiler('while.asda')

    env = dict(os.environ)
    env['PYTHONPATH'] = str(examples_dir.parent)
    process = subprocess.Popen([sys.executable, '-m', 'pyasda', compiled],
                               stdout=subprocess.PIPE, env=env)

    # must check many lines to make sure it's not doing something dumb
    #
    # for example, if while was implemented with python's recursion, it would
    # crash before 1000 iterations because sys.getrecursionlimit() is 100 by
    # default
    for lel in range(2000):
        assert process.stdout.readline() == b'Yay\n'
    process.kill()


def test_all_examples_tested():
    for path in examples_dir.iterdir():
        if (path.suffix == '.asda' and
                ('test_%s_example' % path.stem) not in globals()):
            raise RuntimeError(
                "test_%s_example() not found, maybe %s is not tested?"
                % (path.stem, path.name))
