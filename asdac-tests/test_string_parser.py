import random

import pytest

from asdac import string_parser
from asdac.common import CompileError, Location


LINE = 123
COLUMN = 456


def location(start_offset, end_offset):
    return Location('test file', LINE, COLUMN + start_offset,
                    LINE, COLUMN + end_offset)


def parse(string):
    return string_parser.parse(string, location(0, len(string)))


# the argument is not called location because there's a global location() func
def doesnt_parse(string, message, loc):
    with pytest.raises(CompileError) as error:
        parse(string)
    assert error.value.message == message
    assert error.value.location == loc


def test_escapes():
    assert parse(r'\n\t\\\"') == [
        ('string', '\n\t\\"', location(0, 8)),
    ]


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


def test_errors():
    doesnt_parse('{hello',
                 r"missing }, or maybe you want \{ instead of {",
                 location(0, 6))
    doesnt_parse('{{hello}',
                 r"missing }, or maybe you want \{ instead of {",
                 location(0, 8))
    doesnt_parse('hello}',
                 r"missing {, or maybe you want \} instead of }",
                 location(5, 6))
    doesnt_parse('{hello}}',
                 r"missing {, or maybe you want \} instead of }",
                 location(7, 8))

    doesnt_parse(r'\a',
                 r'expected \n, \t, \\ or \"',
                 location(0, 2))
