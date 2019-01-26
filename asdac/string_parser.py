import collections
import re

from asdac import common


_BACKSLASHED = collections.OrderedDict([
    (r'\n', '\n'),
    (r'\t', '\t'),
    (r'\\', '\\'),
    (r'\"', '"'),
])

_TOKEN_REGEX = '|'.join('(?P<%s>%s)' % pair for pair in [
    ('escape', r'\\[%s]' % re.escape(''.join(_BACKSLASHED.keys()))),
    ('interpolate', r'\{[^\{\}]*\}'),
    ('text', r'[^\{\}\\]+'),
    ('error', r'.'),
])


def _or_join(strings):
    *comma_stuff, last = strings
    return ', '.join(comma_stuff) + ' or ' + last


# the string and location must NOT include the beginning and ending "
def parse(string, string_location):
    # this assumes that the string is one-line
    assert string_location.startline == string_location.endline
    assert (string_location.startcolumn + len(string) ==
            string_location.endcolumn)
    assert '\n' not in string       # but may contain '\\n', aka r'\n'

    def create_location(start_offset, end_offset):
        if end_offset is None:
            end = string_location.endcolumn
        else:
            end = string_location.startcolumn + end_offset

        return common.Location(
            string_location.filename, string_location.startline,
            string_location.startcolumn + start_offset,
            string_location.endline, end)

    result = []
    for match in re.finditer(_TOKEN_REGEX, string):
        kind = match.lastgroup
        value = match.group(kind)

        if kind == 'escape':
            result.append(('string', _BACKSLASHED[value], create_location(
                match.start(), match.end())))

        elif kind == 'interpolate':
            result.append(('code', value[1:-1], create_location(
                match.start() + 1, match.end() - 1)))

        elif kind == 'text':
            result.append(('string', value, create_location(
                match.start(), match.end())))

        elif kind == 'error':
            if value == '\\':
                raise common.CompileError(
                    "expected " + _or_join(_BACKSLASHED.keys()),
                    create_location(match.start(), match.start() + 2))
            if value in {'{', '}'}:
                raise common.CompileError(
                    r"missing %s, or maybe you want \%s instead of %s" % (
                        {'{': '}', '}': '{'}[value], value, value),
                    create_location(match.start(), None))
            raise NotImplementedError(value)    # pragma: no cover

        else:
            raise NotImplementedError(kind)     # pragma: no cover

    # turn [('string', 'a'), ('string', 'b')] to [('string', 'ab')]
    # this is needed for strings like "hello\nworld"
    merged = []
    for kind, value, location in result:
        if merged and merged[-1][0] == 'string' and kind == 'string':
            merged[-1] = ('string', merged[-1][1] + value,
                          merged[-1][2] + location)
        else:
            merged.append((kind, value, location))

    return merged
