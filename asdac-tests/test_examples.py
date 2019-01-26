import os
import shutil
import sys

import asdac.__main__


examples_dir = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'examples')


def create_test_func(sourcefilename):
    def test_func(tmp_path, monkeypatch, capsys):
        monkeypatch.chdir(tmp_path)
        shutil.copy(os.path.join(examples_dir, sourcefilename), '.')

        monkeypatch.setattr(sys, 'argv', ['asdac', sourcefilename])
        asdac.__main__.main()

        out, err = capsys.readouterr()
        assert not out
        assert err == 'Compiling: %s --> asda-compiled%s%sc\n' % (
            sourcefilename, os.sep, sourcefilename)

        with open(os.path.join('asda-compiled', sourcefilename + 'c'),
                  'rb') as f:
            bytecode = f.read()

        # TODO: run the bytecode or something, but then it's no longer
        #       purely an asdac test
        assert bytecode.startswith(b'asda')

    # magic is fun
    test_func.__name__ = 'test_' + sourcefilename.replace('.', '_dot_')
    test_func.__qualname__ = test_func.__name__
    globals()[test_func.__name__] = test_func


for file in os.listdir(examples_dir):
    if file.endswith('.asda'):
        create_test_func(file)
