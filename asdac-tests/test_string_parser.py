from asdac.common import Compilation, Location


START_OFFSET = 123


# lol
class AnyCompilation(Compilation):
    def __init__(self): pass

    def __eq__(self, other): return isinstance(other, Compilation)


def location(start_offset, end_offset, *, compilation=AnyCompilation()):
    return Location(compilation, START_OFFSET + start_offset,
                    end_offset - start_offset)


def test_escapes(compiler):
    parts = ['\n', '\t', '\\', '"', '{', '}']
    assert compiler.string_parse(r'\n\t\\\"\{\}') == [
        ('string', part, location(2*index, 2*index + 2))
        for index, part in enumerate(parts)]


def test_interpolation(compiler):
    assert compiler.string_parse('abcd') == [
        ('string', 'abcd', location(0, 4)),
    ]
    assert compiler.string_parse('{ab}cd') == [
        ('code', 'ab', location(1, 3)),
        ('string', 'cd', location(4, 6)),
    ]
    assert compiler.string_parse('ab{cd}') == [
        ('string', 'ab', location(0, 2)),
        ('code', 'cd', location(3, 5)),
    ]
    assert compiler.string_parse('{x} and {y}{z}') == [
        ('code', 'x', location(1, 2)),
        ('string', ' and ', location(3, 8)),
        ('code', 'y', location(9, 10)),
        ('code', 'z', location(12, 13)),
    ]
    assert compiler.string_parse('') == []
