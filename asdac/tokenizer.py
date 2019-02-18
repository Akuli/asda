import re
import sys

import more_itertools
import regex

import sly

from . import common, string_parser


_LETTER_REGEX = r'\p{Lu}|\p{Ll}|\p{Lo}'    # not available in stdlib re module


class AsdaLexer(sly.Lexer):
    regex_module = regex

    tokens = {INTEGER, ID, OP, KEYWORD, STRING, IGNORE1, NEWLINE,   # noqa
              INDENT, IGNORE2}      # noqa

    INTEGER = r'[1-9][0-9]*|0'
    ID = r'(?:%s|_)(?:%s|[0-9_])*' % (_LETTER_REGEX, _LETTER_REGEX)
    OP = r'==|!=|->|[+\-`*/;=():.,\[\]]'
    STRING = '"' + string_parser.CONTENT_REGEX + '"'
    BLANK_LINE = r'(?<=\n|^) *(?:#.*)?\n'
    NEWLINE = r'\n'
    INDENT = r'(?<=\n|^) +'
    IGNORE_SPACES = r' '
    IGNORE_COMMENT = r'#.*'

    ID['let'] = KEYWORD     # noqa
    ID['if'] = KEYWORD      # noqa
    ID['elif'] = KEYWORD    # noqa
    ID['else'] = KEYWORD    # noqa
    ID['while'] = KEYWORD   # noqa
    ID['for'] = KEYWORD     # noqa
    ID['void'] = KEYWORD    # noqa
    ID['return'] = KEYWORD  # noqa
    ID['func'] = KEYWORD    # noqa
    ID['yield'] = KEYWORD   # noqa

    def __init__(self, filename):
        super().__init__()
        self.filename = filename

    def BLANK_LINE(self, token):
        self.lineno += 1
        self.line_start_offset = token.index + len(token.value)
        return None

    def NEWLINE(self, token):
        self.lineno += 1
        self.line_start_offset = token.index + len(token.value)
        return token

    def IGNORE_SPACES(self, token):
        return None

    def IGNORE_COMMENT(self, token):
        return None

    def error(self, token):
        assert token.value
        if token.value.startswith('"'):
            # because error messages would be very confusing without this
            try:
                length = token.value.index('\n')
            except IndexError:
                length = len(token.value)
            raise common.CompileError("invalid string", common.Location(
                self.filename, token.index, length))

        location = common.Location(self.filename, token.index, 1)
        if token.value[0].isprintable():
            raise common.CompileError(
                # TODO: this is confusing if token.value[0] == "'"
                "unexpected '%s'" % token.value[0], location)
        raise common.CompileError(
            "unexpected character U+%04X" % ord(token.value[0]), location)


# tabs are disallowed because they aren't used for indentation and you can use
# "\t" to get a string that contains a tab
def _tab_check(filename, code, initial_offset):
    try:
        first_tab_offset = initial_offset + code.index('\t')
    except ValueError:
        return

    raise common.CompileError("tabs are not allowed in asda code",
                              common.Location(filename, first_tab_offset, 1))


# not to be confused with sly's tokens
class Token:

    def __init__(self, kind, value, index):
        assert isinstance(index, int)
        # TODO: this relies heavily on sly implementation details, better way?
        fake_sly_token = sly.lex.Token()
        fake_sly_token.type = kind
        fake_sly_token.value = value
        fake_sly_token.lineno = 1
        fake_sly_token.index = index
        self._init_from_sly_token(fake_sly_token)

    @classmethod
    def _from_sly_token(cls, *args):
        self = cls.__new__(cls)  # create new instance without calling __init__
        self._init_from_sly_token(*args)
        return self

    def _init_from_sly_token(self, sly_token):
        self.kind = sly_token.type
        self.value = sly_token.value
        self.index = sly_token.index
        self.sly_token = sly_token

    def __repr__(self):
        return '<Token: kind=%r, value=%r, index=%r>' % (
            self.kind, self.value, self.index)

    # for testing
    def __eq__(self, other):
        if not isinstance(other, Token):
            return NotImplemented
        return ((self.kind, self.value, self.index) ==
                (other.kind, other.value, other.index))


def _raw_tokenize(filename, code, initial_offset):
    _tab_check(filename, code, initial_offset)

    if not code.endswith('\n'):
        code += '\n'

    lexer = AsdaLexer(filename)
    for sly_token in lexer.tokenize(code):
        sly_token.index += initial_offset
        yield Token._from_sly_token(sly_token)


def _handle_indents_and_dedents(filename, tokens, initial_offset):
    # this code took a while to figure out... don't ask me to comment it more
    indent_levels = [0]
    new_line_starting = True
    line_start_offset = initial_offset

    for token in tokens:
        if token.kind == 'NEWLINE':
            assert not new_line_starting, "_raw_tokenize() doesn't work"
            new_line_starting = True
            line_start_offset = token.index + len(token.value)
            yield token

        elif new_line_starting:
            if token.kind == 'INDENT':
                indent_level = len(token.value)
                offset = token.index
                value = token.value
            else:
                indent_level = 0
                offset = line_start_offset
                value = ''

            location = common.Location(filename, offset, len(value))

            if indent_level > indent_levels[-1]:
                yield Token('INDENT', value, offset)
                indent_levels.append(len(value))

            elif indent_level < indent_levels[-1]:
                if indent_level not in indent_levels:
                    raise common.CompileError(
                        "the indentation is wrong", location)
                while indent_level != indent_levels[-1]:
                    yield Token('DEDENT', value, offset)
                    del indent_levels[-1]

            if token.kind != 'INDENT':
                yield token

            new_line_starting = False

        else:
            yield token

    while indent_levels != [0]:
        yield Token('DEDENT', '', line_start_offset)
        del indent_levels[-1]


def _get_location(filename, token):
    return common.Location(filename, token.index, len(token.value))


# the only allowed sequence that contains colon or indent is: colon \n indent
def _check_colons(filename, tokens):
    staggered = more_itertools.stagger(tokens, offsets=(-2, -1, 0))
    for token1, token2, token3 in staggered:
        assert token3 is not None

        if token3.kind == 'INDENT':
            if (token1 is None or
                    token2 is None or
                    token1.kind != 'OP' or
                    token1.value != ':' or
                    token2.kind != 'NEWLINE'):
                raise common.CompileError(
                    "indent without : and newline",
                    _get_location(filename, token3))

        if token1 is not None and token1.kind == 'OP' and token1.value == ':':
            assert token2 is not None and token3 is not None
            if token2.kind != 'NEWLINE' or token3.kind != 'INDENT':
                raise common.CompileError(
                    ": without newline and indent",
                    _get_location(filename, token1))

        yield token3


# to make rest of the code simpler, 'colon \n indent' sequences are
# replaced with just indents
def _remove_colons(tokens):
    staggered = more_itertools.stagger(tokens, offsets=(0, 1, 2), longest=True)
    for token1, token2, token3 in staggered:
        # that is, ignore some stuff that comes before indents
        if (
          (token2 is None or token2.kind != 'INDENT') and
          (token3 is None or token3.kind != 'INDENT')):
            yield token1


def tokenize(filename, code, *, initial_offset=0):
    assert initial_offset >= 0
    tokens = _raw_tokenize(filename, code, initial_offset)
    tokens = _handle_indents_and_dedents(filename, tokens, initial_offset)
    tokens = _check_colons(filename, tokens)
    tokens = _remove_colons(tokens)
    return tokens
