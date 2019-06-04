# this comment suppresses all of flake8 for this file:
# flake8: noqa

import collections
import contextlib
import enum
import functools
import itertools
import operator
import os

import more_itertools
import sly

from . import common, string_parser, tokenizer


def _astclass(name, fields):
    return collections.namedtuple(name, ['location'] + fields)


Integer = _astclass('Integer', ['python_int'])
String = _astclass('String', ['python_string'])
StrJoin = _astclass('StrJoin', ['parts'])
Let = _astclass('Let', ['varname', 'value', 'export'])
SetVar = _astclass('SetVar', ['varname', 'value'])
GetVar = _astclass('GetVar', ['varname'])
GetAttr = _astclass('GetAttr', ['obj', 'attrname'])
GetType = _astclass('GetType', ['name'])
# FromGeneric represents looking up a generic function or generic type
FromGeneric = _astclass('FromGeneric', ['name', 'types'])
FuncCall = _astclass('FuncCall', ['function', 'args'])
FuncDefinition = _astclass('FuncDefinition', ['args', 'returntype', 'body'])
Return = _astclass('Return', ['value'])
Yield = _astclass('Yield', ['value'])
VoidStatement = _astclass('VoidStatement', [])
# ifs is a list of (condition, body) pairs, where body is a list
If = _astclass('If', ['ifs', 'else_body'])
While = _astclass('While', ['condition', 'body'])
For = _astclass('For', ['init', 'cond', 'incr', 'body'])
Import = _astclass('Import', ['source_path', 'varname'])
PrefixOperator = _astclass('PrefixOperator', ['operator', 'expression'])
BinaryOperator = _astclass('BinaryOperator', ['operator', 'lhs', 'rhs'])


def _duplicate_check(iterable, what_are_they):
    seen = set()
    for name, location in iterable:
        if name in seen:
            raise common.CompileError(
                "repeated %s name: %s" % (what_are_they, name), location)
        seen.add(name)


def _to_string(parsed):
    location = parsed.location      # because pep8 line length
    return FuncCall(location, GetAttr(location, parsed, 'to_string'), [])


class TokenIterator:

    def __init__(self, iterable):
        self._iterator = iter(iterable)
        self._include_whitespace_flag = True

    def copy(self):
        self._iterator, copy = itertools.tee(self._iterator)
        result = TokenIterator(copy)
        result._include_whitespace_flag = self._include_whitespace_flag
        return result

    def peek(self):
        return self.copy().next_token()

    def next_token(self):
        try:
            token = next(self._iterator)
            while (token.type in {'NEWLINE', 'INDENT', 'DEDENT'} and
                   not self._include_whitespace_flag):
                token = next(self._iterator)
        except StopIteration:
            raise common.CompileError("unexpected end of file", None)

        return token

    def eof(self):
        try:
            self.copy().next_token()
            return False
        except common.CompileError:
            return True

    @contextlib.contextmanager
    def include_whitespace(self, boolean):
        old_value = self._include_whitespace_flag
        self._include_whitespace_flag = boolean
        try:
            yield
        finally:
            assert self._include_whitespace_flag is boolean
            self._include_whitespace_flag = old_value


# the values can be used as bit flags, e.g. PREFIX | BINARY
#
# i would use enum.IntFlag but it's new in python 3.6, and other stuff works
# on python works 3.5
class OperatorKind(enum.IntEnum):
    PREFIX = 1 << 0     # -x
    BINARY = 1 << 1     # x + y
    TERNARY = 1 << 2    # x `y` z


_PRECEDENCE_LIST = [
    # lists of items like (operator, has_lhs, has_rhs)
    #
    # has_lhs is None for e.g. '-', because x-y and -x are valid expressions
    [('*', OperatorKind.BINARY)],
    [('+', OperatorKind.BINARY),
     ('-', OperatorKind.PREFIX | OperatorKind.BINARY)],
    [('==', OperatorKind.BINARY),
     ('!=', OperatorKind.BINARY)],
]


def _find_adjacent_items(the_list, key):
    for item1, item2 in zip(the_list, the_list[1:]):
        if key(item1, item2):
            return (item1, item2)
    return None


class AsdaParser:

    def __init__(self, compilation, token_generator):
        self.compilation = compilation
        self.tokens = TokenIterator(token_generator)
        self.import_paths = []

    def _token2location(self, token):
        return common.Location(
            self.compilation, token.index, len(token.value))

    def _handle_string_literal(self, string, location, allow_curly_braces):
        assert len(string) >= 2 and string[0] == '"' and string[-1] == '"'
        content = string[1:-1]
        content_location = common.Location(
            location.compilation, location.offset + 1, location.length - 2)

        parts = []
        for kind, value, part_location in string_parser.parse(
                content, content_location):
            if kind == 'string':
                parts.append(String(part_location, value))

            elif kind == 'code':
                if not allow_curly_braces:
                    raise common.CompileError(
                        "cannot use {...} strings here", part_location)

                tokens = tokenizer.tokenize(
                    part_location.compilation, value,
                    initial_offset=part_location.offset)

                parser = AsdaParser(self.compilation, tokens)
                if parser.tokens.eof():
                    raise common.CompileError(
                        "you must put some code between { and }",
                        part_location)

                expression = parser.parse_expression()
                newline = parser.tokens.next_token()    # added by tokenizer
                if newline.type != 'NEWLINE' or not parser.tokens.eof():
                    raise common.CompileError(
                        "you must put exactly one expression between { and }",
                        part_location)

                parts.append(_to_string(expression))

            else:   # pragma: no cover
                raise NotImplementedError(kind)

        return parts

    def parse_type(self):
        # TODO: generic types?
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise common.CompileError(
                "invalid type", self._token2location(name))
        return GetType(self._token2location(name), name.value)

    def parse_commasep_in_parens(self, item_callback):
        lparen = self.tokens.next_token()
        if lparen.value != '(':
            raise common.CompileError(
                "should be '('", self._token2location(lparen))

        with self.tokens.include_whitespace(False):
            result = []

            # doesn't need an eof check because tokenizer matches parentheses
            while self.tokens.peek().value != ')':
                if result:
                    comma = self.tokens.next_token()
                    if comma.value != ',':
                        raise common.CompileError(
                            "should be ',' or ')'",
                            self._token2location(comma))

                result.append(item_callback())

            rparen = self.tokens.next_token()
            if rparen.value != ')':
                raise common.CompileError(
                    "should be ',' or ')'", self._token2location(rparen))

        return (lparen, result, rparen)

    def parse_argument_definition(self):
        tybe = self.parse_type()
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise common.CompileError(
                "invalid variable name", self._token2location(name))
        location = tybe.location + self._token2location(name)
        return (tybe, name.value, location)

    def expression_without_operators_coming_up(self):
        if self.tokens.peek().value == '(':
            # could be a function or parentheses for predecence, both are
            # expressions
            return True

        if self.tokens.peek().type in {'INTEGER', 'STRING', 'ID'}:
            return True

        return False

    def operator_from_precedence_list_coming_up(self):
        if self.tokens.eof():
            return False

        for ops in _PRECEDENCE_LIST:
            for op, precedence in ops:
                if self.tokens.peek().value == op:
                    return True
        return False

    # remember to update operator_or_expression_without_operators_coming_up()
    # whenever you change this method!
    def parse_expression_without_operators_or_calls(self):
        if self.tokens.peek().value == '(':
            # it is a function definition when there is '->' after matching ')'
            copy = self.tokens.copy()
            copy.next_token()       # '('
            paren_count = 1

            while paren_count != 0:
                # tokenizer makes sure that the parens are matched, so this
                # can't fail with end of file
                token = copy.next_token()

                if token.value == '(':
                    paren_count += 1
                if token.value == ')':
                    paren_count -= 1

            if (not copy.eof()) and copy.next_token().value == '->':
                # it is a function
                lparen, args, rparen = self.parse_commasep_in_parens(
                    self.parse_argument_definition)
                arrow = self.tokens.next_token()
                assert arrow.value == '->', arrow

                if self.tokens.peek().value == 'void':
                    returntype = None
                    location = (self._token2location(lparen) +
                                self._token2location(self.tokens.next_token()))
                else:
                    returntype = self.parse_type()
                    location = self._token2location(lparen) + returntype.location

                body = self.parse_block()
                return FuncDefinition(location, args, returntype, body)

            else:
                lparen = self.tokens.next_token()
                assert lparen.value == '('

                with self.tokens.include_whitespace(False):
                    result = self.parse_expression()
                    rparen = self.tokens.next_token()

                if rparen.value != ')':
                    raise common.CompileError(
                        "should be ')'", self._token2location(rparen))

                return result

        if self.tokens.peek().type == 'INTEGER':
            token = self.tokens.next_token()
            return Integer(self._token2location(token), int(token.value))

        if self.tokens.peek().type == 'STRING':
            token = self.tokens.next_token()
            parts = self._handle_string_literal(
                token.value, self._token2location(token),
                allow_curly_braces=True)
            location = self._token2location(token)

            if len(parts) == 0:     # empty string
                return String(location, '')
            if len(parts) == 1:
                return parts[0]._replace(location=location)
            return StrJoin(location, parts)

        if self.tokens.peek().type == 'ID':
            token = self.tokens.next_token()
            return GetVar(self._token2location(token), token.value)

        raise common.CompileError(
            "invalid syntax", self._token2location(self.tokens.next_token()))

    def parse_expression_without_operators(self):
        result = self.parse_expression_without_operators_or_calls()

        # this is part of parsing an expression because the list of function
        # arguments isn't a valid expression, so it's hard to do this with
        # operators
        while (not self.tokens.eof()) and self.tokens.peek().value == '(':
            lparen, args, rparen = self.parse_commasep_in_parens(
                self.parse_expression)
            result = FuncCall(
                result.location + self._token2location(rparen),
                result, args)

        return result

    def parse_expression(self):
        parts = []      # (is it expression, operator token or expression node)
        while True:
            expression_coming = self.expression_without_operators_coming_up()
            operator_coming = self.operator_from_precedence_list_coming_up()
            assert not (expression_coming and operator_coming)

            if expression_coming:
                parts.append((True, self.parse_expression_without_operators()))
            elif operator_coming:
                parts.append((False, self.tokens.next_token()))
            else:
                break

        if not parts:
            # next_token() may raise CompileError for end of file, that's fine
            not_expression = self.tokens.next_token()
            raise common.CompileError("should be an expression",
                                      self._token2location(not_expression))

        # there must not be two expressions next to each other without an
        # operator between
        adjacent_expression_parts = _find_adjacent_items(
            parts, (lambda part1, part2: part1[0] and part2[0]))
        if adjacent_expression_parts is not None:
            (junk1, bad1), (junk2, bad2) = adjacent_expression_parts
            # if you have an idea for a better error message, add that here
            raise common.CompileError(
                "invalid syntax", bad1.location + bad2.location)

        # welcome to my hell
        for op_kind_pairs in _PRECEDENCE_LIST:
            ops = [op for op, kind in op_kind_pairs]

            while True:
                for index, (is_expression, token) in enumerate(parts):
                    if is_expression:
                        continue
                    try:
                        i = ops.index(token.value)
                    except ValueError:
                        continue
                    kind = op_kind_pairs[i][1]
                    break
                else:
                    break

                # now we have these variables: index, kind, token

                assert kind & OperatorKind.TERNARY == 0, "not implemented"
                location = self._token2location(token)

                if index-1 >= 0 and parts[index-1][0]:
                    before = parts[index-1][1]
                    assert before is not None
                else:
                    before = None

                if index+1 < len(parts) and parts[index+1][0]:
                    after = parts[index+1][1]
                    assert after is not None
                else:
                    after = None

                if before is None and after is not None:
                    valid = bool(kind & OperatorKind.PREFIX)
                    result = PrefixOperator(location, token.value, after)
                elif before is not None and after is not None:
                    valid = bool(kind & OperatorKind.BINARY)
                    result = BinaryOperator(
                        location, token.value, before, after)
                else:
                    valid = False
                    # result is not needed

                if not valid:
                    raise common.CompileError(
                        "'%s' cannot be used like this" % token.value,
                        location)

                start_index = index if before is None else index-1
                end_index = index + 1 if after is None else index + 2
                assert start_index >= 0
                assert end_index <= len(parts)
                parts[start_index:end_index] = [(True, result)]

        assert len(parts) == 1
        result_is_expression, result = parts[0]
        assert result_is_expression
        return result

    def parse_1line_statement(self):
        if self.tokens.peek().value == 'return':
            return_keyword = self.tokens.next_token()
            value = self.parse_expression()
            return Return(
                self._token2location(return_keyword) + value.location, value)

        if self.tokens.peek().value == 'let':
            let = self.tokens.next_token()

            varname_token = self.tokens.next_token()
            if varname_token.type != 'ID':
                raise common.CompileError(
                    "invalid variable name",
                    self._token2location(varname_token))

            eq = self.tokens.next_token()
            if eq.value != '=':
                raise common.CompileError(
                    "should be '='", self._token2location(eq))

            value = self.parse_expression()

            return Let(self._token2location(let), varname_token.value, value,
                       export=False)

        if self.tokens.peek().value == 'export':
            export_token = self.tokens.next_token()
            if self.tokens.peek().value != 'let':
                raise common.CompileError(
                    "expected 'let'", self._token2location(self.tokens.peek()))

            let = self.parse_1line_statement()
            assert isinstance(let, Let)
            return let._replace(export=True)

        # TODO: more different kinds of statements
        return self.parse_expression()

    def parse_statement(self):
        if self.tokens.peek().value == 'if':
            if_location = self._token2location(self.tokens.next_token())
            condition = self.parse_expression()
            body = self.parse_block(consume_newline=True)
            ifs = [(condition, body)]

            while ((not self.tokens.eof()) and
                   self.tokens.peek().value == 'elif'):
                self.tokens.next_token()    # 'elif'
                ifs.append((self.parse_expression(),
                            self.parse_block(consume_newline=True)))

            if (not self.tokens.eof()) and self.tokens.peek().value == 'else':
                self.tokens.next_token()    # 'else'
                else_body = self.parse_block(consume_newline=True)
            else:
                else_body = []

            return If(if_location, ifs, else_body)

        # TODO: more different kinds of statements

        result = self.parse_1line_statement()

        newline = self.tokens.next_token()
        if newline.type != 'NEWLINE':
            raise common.CompileError(
                "expected a newline", self._token2location(newline))
        return result

    def parse_block(self, *, consume_newline=False):
        with self.tokens.include_whitespace(True):
            indent = self.tokens.next_token()
            if indent.type != 'INDENT':
                raise common.CompileError(
                    "expected an indent", self._token2location(indent))

            result = []
            while self.tokens.peek().type != 'DEDENT':
                result.append(self.parse_statement())

            dedent = self.tokens.next_token()
            assert dedent.type == 'DEDENT'

            if consume_newline:
                newline = self.tokens.next_token()
                assert newline.type == 'NEWLINE', "tokenizer doesn't work"

            return result

    def parse_statements(self):
        while True:
            try:
                self.tokens.peek()
            except common.CompileError:     # end of file, compilation done
                break

            yield self.parse_statement()


def parse(compilation, code):
    parser = AsdaParser(compilation, tokenizer.tokenize(compilation, code))
    statements = list(parser.parse_statements())    # must not be lazy iterator
    return (statements, parser.import_paths)
