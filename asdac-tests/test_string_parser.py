import pytest

from asdac import string_parser
from asdac.common import Compilation, CompileError, Location


START_OFFSET = 123


# lol
class AnyCompilation(Compilation):
    def __init__(self): pass
    def __eq__(self, other): return isinstance(other, Compilation)


def location(start_offset, end_offset, *, compilation=AnyCompilation()):
    return Location(compilation, START_OFFSET + start_offset,
                    end_offset - start_offset)


def parse(string):
    loc = location(0, len(string), compilation=Compilation('test file', '.'))
    return list(string_parser.parse(string, loc))


# the argument is not called location because there's a global location() func
def doesnt_parse(string, message, loc):
    with pytest.raises(CompileError) as error:
        parse(string)
    assert error.value.message == message
    assert error.value.location == loc


def test_escapes():
    parts = ['\n', '\t', '\\', '"', '{', '}']
    assert parse(r'\n\t\\\"\{\}') == [
        ('string', part, location(2*index, 2*index + 2))
        for index, part in enumerate(parts)]


def test_interpolation():
    assert parse('abcd') == [
        ('string', 'abcd', location(0, 4)),
    ]
    assert parse('{ab}cd') == [
        ('code', 'ab', location(1, 3)),
        ('string', 'cd', location(4, 6)),
    ]
    assert parse('ab{cd}') == [
        ('string', 'ab', location(0, 2)),
        ('code', 'cd', location(3, 5)),
    ]
    assert parse('{x} and {y}{z}') == [
        ('code', 'x', location(1, 2)),
        ('string', ' and ', location(3, 8)),
        ('code', 'y', location(9, 10)),
        ('code', 'z', location(12, 13)),
    ]
    assert parse('') == []
