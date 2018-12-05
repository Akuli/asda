import collections
import re

import more_itertools

from . import common


_TOKEN_REGEX = '|'.join('(?P<%s>%s)' % pair for pair in [
    ('integer', r'[1-9][0-9]*|0'),
    ('id', r'[^\W\d]\w*'),
    ('op', r'[;=():.,\[\]]'),
    ('string', r'"[^"]*?"'),
    ('ignore1', r'^[ \t]*(?:#.*)?\n'),
    ('newline', r'\n'),
    ('indent', r'^ +'),
    ('ignore2', r'[ \t]+'),
    ('ignore3', r'#.*'),
    ('error', r'.'),
])

Token = collections.namedtuple('Token', ['kind', 'value', 'location'])


def _raw_tokenize(filename, code):
    lineno = 1
    line_offset = 0

    for match in re.finditer(_TOKEN_REGEX, code, flags=re.MULTILINE):
        kind = match.lastgroup
        value = match.group(kind)
        startcolumn = match.start() - line_offset
        endcolumn = match.end() - line_offset

        if '\n' in value:
            assert value.count('\n') == 1 and value.endswith('\n')
            location = common.Location(
                filename,
                lineno, startcolumn,
                lineno + 1, 0,
            )
            lineno += 1
            line_offset = match.end()
        else:
            location = common.Location(
                filename, lineno, startcolumn, lineno, endcolumn)

        if kind == 'error':
            raise common.CompileError("unexpected %s" % value, location)
        elif kind.startswith('ignore'):
            pass
        else:
            if kind == 'id' and value in {'let', 'if', 'else', 'while', 'for',
                                          'void', 'return', 'generator'}:
                kind = 'keyword'
            yield Token(kind, value, location)


def _handle_indents_and_dedents(filename, tokens):
    # this code took a while to figure out... don't ask me to comment it more
    indent_levels = [0]
    new_line_starting = True
    last_lineno = None

    for token in tokens:
        last_lineno = token.location.endline
        if token.kind == 'newline':
            assert not new_line_starting, "_raw_tokenize() doesn't work"
            new_line_starting = True
            yield token
            continue

        if new_line_starting:
            if token.kind == 'indent':
                indent_level = len(token.value)
                location = token.location
                value = token.value
            else:
                indent_level = 0
                lineno = token.location.startline
                location = common.Location(token.location.filename,
                                           lineno, 0, lineno, 0)
                value = ''

            if indent_level > indent_levels[-1]:
                yield Token('indent', value, location)
                indent_levels.append(len(value))

            elif indent_level < indent_levels[-1]:
                if indent_level not in indent_levels:
                    raise common.CompileError(
                        "the indentation is wrong", location)
                while indent_level != indent_levels[-1]:
                    yield Token('dedent', value, location)
                    del indent_levels[-1]

            if token.kind != 'indent':
                yield token

            new_line_starting = False

        else:
            yield token

    while indent_levels != [0]:
        assert last_lineno is not None
        yield Token('dedent', '',
                    common.Location(filename, last_lineno, 0, last_lineno, 0))
        del indent_levels[-1]


# the only allowed sequence that contains colon or indent is: colon \n indent
def _check_colons(tokens):
    staggered = more_itertools.stagger(tokens, offsets=(-2, -1, 0))
    for token1, token2, token3 in staggered:
        assert token3 is not None

        if token3.kind == 'indent':
            if (token1 is None or
                    token2 is None or
                    token1.kind != 'op' or
                    token1.value != ':' or
                    token2.kind != 'newline'):
                raise common.CompileError(
                    "indent without : and newline", token3.location)

        if token1 is not None and token1.kind == 'op' and token1.value == ':':
            assert token2 is not None and token3 is not None
            if token2.kind != 'newline' or token3.kind != 'indent':
                raise common.CompileError(
                    ": without newline and indent", token1.location)

        yield token3


# to make rest of the code simpler, 'colon \n indent' sequences are
# replaced with just indents
def _remove_colons(tokens):
    staggered = more_itertools.stagger(tokens, offsets=(0, 1, 2), longest=True)
    for token1, token2, token3 in staggered:
        # that is, ignore some stuff that comes before indents
        if (
          (token2 is None or token2.kind != 'indent') and
          (token3 is None or token3.kind != 'indent')):
            yield token1


def tokenize(filename, code):
    tokens = _raw_tokenize(filename, code)
    tokens = _handle_indents_and_dedents(filename, tokens)
    tokens = _check_colons(tokens)
    tokens = _remove_colons(tokens)
    return tokens
