import collections
import enum
import re
import typing

from asdac import common

# keys are valid regex syntax AND valid asda string content syntax, lol
_BACKSLASHED = {
    r'\n': '\n',
    r'\t': '\t',
    r'\\': '\\',
    r'\"': '"',
    r'\{': '{',
    r'\}': '}',
}

_NOT_SPECIAL = r'[^{}\\"\n]'
_REGEXES = [
    ('escape', '|'.join(map(re.escape, _BACKSLASHED.keys()))),
    # docs/syntax.md says that the code consists of 1 or more characters, but
    # this does * instead of + because empty code will fail later anyway, and
    # less special cases is nice
    ('interpolate', r'\{%s*\}' % _NOT_SPECIAL),
    ('text', r'%s+' % _NOT_SPECIAL),
]
CONTENT_REGEX = '(?:%s)*' % '|'.join(regex for name, regex in _REGEXES)
_PARSING_REGEX = '|'.join(
    '(?P<%s>%s)' % pair for pair in (_REGEXES + [('error', '.')]))


class ContentKind(enum.Enum):
    STRING = enum.auto()
    CODE = enum.auto()


# the string and location must NOT include the beginning and ending "
#
# the result may be e.g. this for "a\nb":
#
#    [('string', 'a', some location),
#     ('string', '\n', some location),
#     ('string', 'b', some location)]
#
# but that should get optimized away later
def parse(
    string: str,
    string_location: common.Location,
) -> typing.Iterator[typing.Tuple[ContentKind, str, common.Location]]:

    # this assumes that the string is one-line
    assert '\n' not in string       # but may contain '\\n', aka r'\n'
    assert len(string) == string_location.length

    def create_location(start_offset: int, end_offset: int) -> common.Location:
        return common.Location(
            string_location.compilation, string_location.offset + start_offset,
            end_offset - start_offset)

    for match in re.finditer(_PARSING_REGEX, string):
        kind = match.lastgroup
        assert kind is not None     # mypy notices this assert, nice
        value = match.group(kind)

        if kind == 'escape':
            yield (ContentKind.STRING, _BACKSLASHED[value],
                   create_location(match.start(), match.end()))

        elif kind == 'interpolate':
            yield ((ContentKind.CODE, value[1:-1], create_location(
                match.start() + 1, match.end() - 1)))

        elif kind == 'text':
            yield (ContentKind.STRING, value,
                   create_location(match.start(), match.end()))

        else:
            raise NotImplementedError(kind)     # pragma: no cover
