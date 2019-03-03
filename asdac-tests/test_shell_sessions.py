# pytest file that runs the things in shell-sessions/
import codecs
import os
import re
import shutil
import sys
import time

import pytest

import asdac.__main__

sessions_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            'shell-sessions')


@pytest.fixture
def shell_session_environment(tmp_path):
    os.chdir(str(tmp_path))
    for file in os.listdir(os.path.join(sessions_dir, 'files')):
        shutil.copy(os.path.join(sessions_dir, 'files', file), '.')
    with open('bom.asda', 'wb') as file:
        file.write(codecs.BOM_UTF8 + b'print("Hello")\n')
    with open('bombom.asda', 'wb') as file:
        file.write(codecs.BOM_UTF8 + codecs.BOM_UTF8 + b'print("Hello")\n')


def touch(path):
    time.sleep(0.05)    # sometimes fails without this
    os.utime(path, None)


def create_test_func(filename):
    def test_func(shell_session_environment, monkeypatch, capsys):
        with open(os.path.join(sessions_dir, filename + '.txt'), 'r',
                  encoding='utf-8') as file:
            session = file.read().replace(r'<\uFEFF>', '\uFEFF')

        for command, output in re.findall(r'^\$ (.*)\n([^\$]*)', session,
                                          flags=re.MULTILINE):
            program, *args = command.split()
            expected_output = output.rstrip()
            if expected_output:
                expected_output += '\n'

            if program == '#':
                actual_output = ''
            elif program == 'touch':
                touch(*args)
                actual_output = ''
            elif program == 'asdac':
                monkeypatch.setattr(sys, 'argv', ['asdac'] + args)
                try:
                    asdac.__main__.main()
                except SystemExit as e:
                    if isinstance(e.code, str):
                        print(e.code, file=sys.stderr)

                output, errors = capsys.readouterr()
                assert not output
                actual_output = errors.replace(os.sep, '/')
            else:
                raise RuntimeError("unknown program: " + program)

            assert expected_output == actual_output

    # magic is fun
    test_func.__name__ = test_func.__qualname__ = (
        'test_%s_session' % filename)
    globals()[test_func.__name__] = test_func


for name, ext in map(os.path.splitext, os.listdir(sessions_dir)):
    if ext == '.txt':
        create_test_func(name)
