import collections
import re

from asdac import common

_BACKSLASHED = collections.OrderedDict([
    (r'\n', '\n'),
    (r'\t', '\t'),
    (r'\\', '\\'),
    (r'\"', '"'),
    (r'\{', '{'),
    (r'\}', '}'),
])

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


# the string and location must NOT include the beginning and ending "
#
# the result may be e.g. this for "a\nb":
#
#    [('string', 'a', some location),
#     ('string', '\n', some location),
#     ('string', 'b', some location)]
#
# but it doesn't matter, or if it does it's probably time to write other
# optimizing code as well, and this can become a part of that then
def parse(string, string_location):
    # this assumes that the string is one-line
    assert '\n' not in string       # but may contain '\\n', aka r'\n'
    assert len(string) == string_location.length

    def create_location(start_offset, end_offset):
        return common.Location(
            string_location.compilation, string_location.offset + start_offset,
            end_offset - start_offset)

    for match in re.finditer(_PARSING_REGEX, string):
        kind = match.lastgroup
        value = match.group(kind)

        if kind == 'escape':
            yield ('string', _BACKSLASHED[value],
                   create_location(match.start(), match.end()))

        elif kind == 'interpolate':
            yield (('code', value[1:-1], create_location(
                match.start() + 1, match.end() - 1)))

        elif kind == 'text':
            yield ('string', value,
                   create_location(match.start(), match.end()))

        else:
            raise NotImplementedError(kind)     # pragma: no cover
