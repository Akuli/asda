import collections

import more_itertools
import regex

from . import common, string_parser


_LETTER_REGEX = r'\p{Lu}|\p{Ll}|\p{Lo}'    # not available in stdlib re module
_ID_REGEX = r'(?:%s|_)(?:%s|[0-9_])*' % (_LETTER_REGEX, _LETTER_REGEX)

_TOKEN_REGEX = '|'.join('(?P<%s>%s)' % pair for pair in [
    ('OPERATOR', r'==|!=|->|[+\-*=`;:.,\[\]()]'),
    ('INTEGER', r'[1-9][0-9]*|0'),
    ('MODULEFUL_ID', r'%s:%s' % (_ID_REGEX, _ID_REGEX)),
    ('ID', _ID_REGEX),
    ('STRING', '"' + string_parser.CONTENT_REGEX + '"'),
    ('IGNORE_BLANK_LINE', r'(?<=\n|^) *(?:#.*)?\n'),
    ('NEWLINE', r'\n'),
    ('INDENT', r'(?<=\n|^) +'),      # DEDENT tokens are created "manually"
    ('IGNORE_SPACES', r' '),
    ('IGNORE_COMMENT', r'#.*'),
    ('ERROR', '.'),
])

# keep this up to date! this is what prevents these from being valid
# variable names
_KEYWORDS = {'let', 'if', 'elif', 'else', 'while', 'for', 'void', 'return',
             'yield', 'import', 'export', 'as', 'try', 'catch'}


Token = collections.namedtuple('Token', ['type', 'value', 'location'])


# tabs are disallowed because they aren't used for indentation and you can use
# "\t" to get a string that contains a tab
def _tab_check(compilation, code, initial_offset):
    try:
        first_tab = initial_offset + code.index('\t')
    except ValueError:
        return

    raise common.CompileError("tabs are not allowed in asda code",
                              common.Location(compilation, first_tab, 1))


def _raw_tokenize(compilation, code, initial_offset):
    _tab_check(compilation, code, initial_offset)

    # remember this part of this code, because many other things rely on this
    if not code.endswith('\n'):
        code += '\n'

    for match in regex.finditer(_TOKEN_REGEX, code):
        token_type = match.lastgroup
        location = common.Location(
            compilation, match.start() + initial_offset,
            match.end() - match.start())
        value = match.group(0)

        if token_type == 'ERROR':
            if value == '"':
                raise common.CompileError(
                    "invalid string", location)
            # the value is 1 character
            if value.isprintable():
                raise common.CompileError(
                    # TODO: this is confusing if token.value == "'"
                    "unexpected '%s'" % value, location)
            raise common.CompileError(
                "unexpected character U+%04X" % ord(value), location)

        if token_type.startswith('IGNORE_'):
            continue

        if value in _KEYWORDS:
            assert token_type == 'ID'
            token_type = 'KEYWORD'

        yield Token(token_type, value, location)


def _match_parens(tokens):
    lparens = list('([{')
    rparens = list(')]}')
    lparen2rparen = dict(zip(lparens, rparens))
    rparen2lparen = dict(zip(rparens, lparens))

    stack = []
    for token in tokens:
        if token.value in lparens:
            stack.append(token)

        if token.value in rparens:
            if not stack:
                raise common.CompileError(
                    "there is no matching '%s'" % rparen2lparen[token.value],
                    token.location)

            matching_paren = stack.pop().value
            if matching_paren != rparen2lparen[token.value]:
                raise common.CompileError(
                    "the matching paren is '%s', not '%s'" % (
                        matching_paren, rparen2lparen[token.value]),
                    token.location)

        yield token

    if stack:
        raise common.CompileError(
            "there is no '%s'" % lparen2rparen[stack[-1].value],
            stack[-1].location)


# This function needs to run before hiad (aka _handle_indents_and_dedents)
# because hiad shouldn't see any of the whitespace between parens, but on the
# other hand, this needs to stop ignoring whitespace whenever there is a block.
# Nothing before hiad knows fully when blocks begin and end, so hiad must tell
# iuw (aka _ignore_unwanted_whitespace) about it somehow. It does that by
# .send()ing it strings.
def _ignore_unwanted_whitespace(tokens):
    ignore_stack = [False]

    for token in tokens:
        if token.value in {'(', '[', '{'}:
            ignore_stack.append(True)
        elif token.value in {')', ']', '}'}:
            # the temporary variable is needed, because disabling asserts
            # disables them completely ... i hope u understood this
            popped = ignore_stack.pop()
            assert popped

        if not (ignore_stack[-1] and token.type in {'NEWLINE', 'INDENT'}):
            while True:
                sent2me = yield token
                if sent2me == 'beginning of block':
                    ignore_stack.append(False)
                elif sent2me == 'end of block':
                    popped = ignore_stack.pop()
                    assert not popped
                elif sent2me is None:
                    # token was received, hiad used next() instead of send()
                    # yes, next(generator) is same as generator.send(None)
                    break
                else:
                    raise RuntimeError("wat")     # pragma: no cover

    assert ignore_stack

    # it is possible that hiad doesn't send enough 'end of block' messages,
    # because it only knows about some dedents after it has went through all
    # the tokens, i.e. ran iuw to the end
    for boolean in ignore_stack[1:]:
        assert not boolean


def _handle_indents_and_dedents(tokens):
    # this code took a while to figure out... don't ask me to comment it more
    indent_levels = [0]
    new_line_starting = True

    token = None    # used below

    for token in tokens:
        assert token is not None
        if token.type == 'NEWLINE':
            assert not new_line_starting, "_raw_tokenize() doesn't work"
            new_line_starting = True
            yield token

        elif new_line_starting:
            if token.type == 'INDENT':
                indent_level = len(token.value)
            else:
                indent_level = 0

            fake_token_location = common.Location(
                token.location.compilation, token.location.offset, 0)

            if indent_level > indent_levels[-1]:
                assert token.type == 'INDENT'
                yield token
                indent_levels.append(indent_level)
                tokens.send('beginning of block')

            elif indent_level < indent_levels[-1]:
                if indent_level not in indent_levels:
                    raise common.CompileError(
                        "the indentation is wrong", token.location)
                while indent_level != indent_levels[-1]:
                    # this is why you shouldn't check if the value of a token
                    # is '\n', you should instead check if the type of the
                    # token is 'NEWLINE'
                    yield Token('DEDENT', '', fake_token_location)
                    yield Token('NEWLINE', '', fake_token_location)
                    del indent_levels[-1]
                    tokens.send('end of block')

            if token.type != 'INDENT':
                yield token

            new_line_starting = False

        else:
            yield token

    # if the previous loop didn't leave a token variable around, it can't have
    # done anything
    if token is None:
        assert indent_levels == [0]
        return

    fake_token_location = common.Location(
        token.location.compilation,
        token.location.offset + token.location.length, 0)

    while indent_levels != [0]:
        yield Token('DEDENT', '', fake_token_location)
        yield Token('NEWLINE', '', fake_token_location)
        del indent_levels[-1]
        # it's not possible to send 'end of block' message anymore, because iuw
        # has already ran to end


# the only allowed sequence that contains colon or indent is: colon \n indent
#
# x:y looks up the exported thing 'y' from a module 'x', but x:y as a whole is
# a MODULEFUL_ID token, there is no colon token involved in that
def _check_colons(tokens):
    staggered = more_itertools.stagger(tokens, offsets=(-2, -1, 0))
    token1 = token2 = token3 = None

    for token1, token2, token3 in staggered:
        assert token3 is not None

        if token3.type == 'INDENT':
            if (token1 is None or
                    token2 is None or
                    token1.value != ':' or
                    token2.type != 'NEWLINE'):
                raise common.CompileError(
                    "indent without : and newline", token3.location)

        if token1 is not None and token1.value == ':':
            assert token2 is not None and token3 is not None
            if token2.type != 'NEWLINE' or token3.type != 'INDENT':
                raise common.CompileError(
                    ": without newline and indent", token1.location)

        yield token3

    # corner case: file may end with ':'
    if token2 is not None and token2.value == ':':
        raise common.CompileError("unexpected end of file", token3.location)


# to make rest of the code simpler, 'colon \n indent' sequences are
# replaced with just indents
def _remove_colons(tokens):
    staggered = more_itertools.stagger(tokens, offsets=(0, 1, 2), longest=True)
    for token1, token2, token3 in staggered:
        # that is, ignore some stuff that comes before indents
        if (
          (token2 is None or token2.type != 'INDENT') and
          (token3 is None or token3.type != 'INDENT')):
            yield token1


def tokenize(compilation, code, *, initial_offset=0):
    assert initial_offset >= 0
    tokens = _raw_tokenize(compilation, code, initial_offset)
    tokens = _match_parens(tokens)
    # these are on the same line because they "depend" on each other a lot
    # i.e. you can't easily add another step between them
    tokens = _handle_indents_and_dedents(_ignore_unwanted_whitespace(tokens))
    tokens = _check_colons(tokens)
    tokens = _remove_colons(tokens)
    return tokens
