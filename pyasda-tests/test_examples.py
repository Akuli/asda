# pytest file that compiles and runs the examples
import os
import re
import shutil
import subprocess
import sys

import pytest

import asdac.__main__
import pyasda.__main__

examples_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'examples')


@pytest.fixture
def compiler(tmp_path, monkeypatch, capsys):
    # python has a built-in compile function, so creating my own 'compile'
    # function would be bad style
    # this is even worse style :DD  MUHAHAA
    def compi1e(filename):
        monkeypatch.chdir(tmp_path)
        for other_file in os.listdir(examples_dir):
            if other_file.endswith('.asda'):
                shutil.copy(os.path.join(examples_dir, other_file), '.')

        monkeypatch.setattr(sys, 'argv', ['asdac', filename])
        asdac.__main__.main()

        out, err = capsys.readouterr()
        assert not out

        match = re.search(r'^Compiling: (.*) --> (.*)\n', err)
        assert all(line.startswith('Compiling: ') for line in err.splitlines())
        assert match is not None, repr(err)
        assert match.group(1) == filename
        return match.group(2)

    return compi1e


@pytest.fixture
def runner(monkeypatch, capsys):
    def run(filename):
        monkeypatch.setattr(sys, 'argv', ['pyasda', filename])
        pyasda.__main__.main()

        out, err = capsys.readouterr()
        assert not err
        return out

    return run


def create_test_func(filename):
    def test_func(compiler, runner):
        compiled = compiler(filename + '.asda')
        output = runner(compiled)

        output_path = os.path.join(examples_dir, 'output', filename + '.txt')
        with open(output_path, 'r') as file:
            assert output == file.read()

    # magic is fun
    test_func.__name__ = test_func.__qualname__ = 'test_%s_example' % filename
    globals()[test_func.__name__] = test_func


for name, ext in map(os.path.splitext,
                     os.listdir(os.path.join(examples_dir, 'output'))):
    if ext == '.txt':
        create_test_func(name)


# can't use the runner that other tests use because running must be interrupted
def test_while_example(compiler):
    compiled = compiler('while.asda')

    env = dict(os.environ)
    env['PYTHONPATH'] = os.path.dirname(examples_dir)
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
    for name, ext in map(os.path.splitext, os.listdir(examples_dir)):
        if ext == '.asda' and ('test_%s_example' % name) not in globals():
            raise RuntimeError(
                "test_%s_example() not found, maybe %s.asda is not tested?"
                % (name, name))
