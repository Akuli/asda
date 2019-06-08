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
# Let's generics is a list of (name, location) tuples, or None
Let = _astclass('Let', ['varname', 'generics', 'value', 'export'])
SetVar = _astclass('SetVar', ['varname', 'value'])
GetVar = _astclass('GetVar', ['varname', 'generics'])
GetAttr = _astclass('GetAttr', ['obj', 'attrname'])
# GetType's generics is a list of other GetTypes, or None
GetType = _astclass('GetType', ['name', 'generics'])
FuncCall = _astclass('FuncCall', ['function', 'args'])
FuncDefinition = _astclass('FuncDefinition', ['args', 'returntype', 'body'])
Return = _astclass('Return', ['value'])
Yield = _astclass('Yield', ['value'])
VoidStatement = _astclass('VoidStatement', [])
# If's ifs is a list of (condition, body) pairs, where body is a list
If = _astclass('If', ['ifs', 'else_body'])
While = _astclass('While', ['condition', 'body'])
For = _astclass('For', ['init', 'cond', 'incr', 'body'])
Import = _astclass('Import', ['source_path', 'varname'])
PrefixOperator = _astclass('PrefixOperator', ['operator', 'expression'])
BinaryOperator = _astclass('BinaryOperator', ['operator', 'lhs', 'rhs'])
TernaryOperator = _astclass('TernaryOperator', ['operator', 'lhs', 'mid',
                                                'rhs'])


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


class _TokenIterator:

    def __init__(self, iterable):
        self._iterator = iter(iterable)

    def copy(self):
        self._iterator, copy = itertools.tee(self._iterator)
        return _TokenIterator(copy)

    def peek(self):
        return self.copy().next_token()

    def next_token(self):
        try:
            return next(self._iterator)
        except StopIteration:
            # i think this code is currently impossible to reach, but that may
            # change in the future without noticing it when writing the
            # changing code
            #
            # TODO: the 'file' in this error message is wrong for an error that
            #       comes from the {...} part of a string literal
            raise common.CompileError("unexpected end of file", None)

    def eof(self):
        # old bug: don't use .next_token() or .peek() and catch CompileError,
        # because that also catches errors from tokenizer
        try:
            next(self.copy()._iterator)
            return False
        except StopIteration:
            return True


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
    [('.', OperatorKind.BINARY)],
    [('`', OperatorKind.TERNARY)],
]


def _find_adjacent_items(the_list, key):
    for item1, item2 in zip(the_list, the_list[1:]):
        if key(item1, item2):
            return (item1, item2)
    return None


class _AsdaParser:

    def __init__(self, compilation, token_generator):
        self.compilation = compilation
        self.tokens = _TokenIterator(token_generator)
        self.import_paths = []

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

                parser = _AsdaParser(self.compilation, tokens)
                if parser.tokens.eof():
                    raise common.CompileError(
                        "you must put some code between { and }",
                        part_location)

                expression = parser.parse_expression()
                newline = parser.tokens.next_token()    # added by tokenizer
                if newline.type != 'NEWLINE' or not parser.tokens.eof():
                    # find the part that was not a part of the expression
                    token_list = [newline]
                    while not parser.tokens.eof():
                        token_list.append(parser.tokens.next_token())

                    assert token_list[-1].type == 'NEWLINE'
                    raise common.CompileError(
                        "invalid syntax",
                        token_list[0].location + token_list[-2].location)

                parts.append(_to_string(expression))

            else:   # pragma: no cover
                raise NotImplementedError(kind)

        return parts

    def parse_commasep_in_parens(self, item_callback, *,
                                 parens='()', allow_empty=True):
        lparen_string, rparen_string = parens

        lparen = self.tokens.next_token()
        assert lparen.value == lparen_string    # should be checked by caller

        result = []

        # doesn't need an eof check because tokenizer matches parentheses
        # an eof error wouldn't matter anyway
        while self.tokens.peek().value != rparen_string:
            if result:
                comma = self.tokens.next_token()
                if comma.value != ',':
                    raise common.CompileError(
                        "should be ',' or '%s'" % rparen_string,
                        comma.location)

            result.append(item_callback())

        rparen = self.tokens.next_token()
        assert rparen.value == rparen_string

        if (not allow_empty) and (not result):
            raise common.CompileError(
                "you must put something between '%s' and '%s'" % (
                    lparen_string, rparen_string),
                lparen.location + rparen.location)

        return (lparen, result, rparen)

    def parse_type(self):
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise common.CompileError("invalid type", name.location)

        if (not self.tokens.eof()) and self.tokens.peek().value == '[':
            lbracket, generics, rbracket = self.parse_commasep_in_parens(
                self.parse_type, parens='[]', allow_empty=False)
            location = name.location + rbracket.location
        else:
            generics = None
            location = name.location

        return GetType(location, name.value, generics)

    def parse_argument_definition(self):
        tybe = self.parse_type()
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise common.CompileError("invalid variable name", name.location)
        location = tybe.location + name.location
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
                _duplicate_check((arg[1:] for arg in args), 'argument')
                arrow = self.tokens.next_token()
                assert arrow.value == '->', arrow

                if self.tokens.peek().value == 'void':
                    returntype = None
                    location = (lparen.location +
                                self.tokens.next_token().location)
                else:
                    returntype = self.parse_type()
                    location = lparen.location + returntype.location

                body = self.parse_block()
                return FuncDefinition(location, args, returntype, body)

            else:
                # parentheses are being used for precedence here
                lparen = self.tokens.next_token()
                assert lparen.value == '('
                result = self.parse_expression()
                rparen = self.tokens.next_token()

                if rparen.value != ')':
                    raise common.CompileError("should be ')'", rparen.location)

                return result

        if self.tokens.peek().type == 'INTEGER':
            token = self.tokens.next_token()
            return Integer(token.location, int(token.value))

        if self.tokens.peek().type == 'STRING':
            token = self.tokens.next_token()
            parts = self._handle_string_literal(
                token.value, token.location, allow_curly_braces=True)

            if len(parts) == 0:     # empty string
                return String(token.location, '')
            if len(parts) == 1:
                return parts[0]._replace(location=token.location)
            return StrJoin(token.location, parts)

        if self.tokens.peek().type == 'ID':
            token = self.tokens.next_token()

            # it's easier to do this here than to do it later
            if self.tokens.peek().value == '[':
                lbracket, generics, rbracket = self.parse_commasep_in_parens(
                    self.parse_type, parens='[]', allow_empty=False)
                location = token.location + rbracket.location
            else:
                generics = None
                location = token.location

            return GetVar(location, token.value, generics)

        raise common.CompileError(
            "invalid syntax", self.tokens.next_token().location)

    def parse_expression_without_operators(self):
        result = self.parse_expression_without_operators_or_calls()

        # this is part of parsing an expression because the list of function
        # arguments isn't a valid expression, so it's hard to do this with
        # operators
        while (not self.tokens.eof()) and self.tokens.peek().value == '(':
            lparen, args, rparen = self.parse_commasep_in_parens(
                self.parse_expression)
            result = FuncCall(result.location + rparen.location, result, args)

        return result

    def operator_helper(self, expression):
        if (isinstance(expression, TernaryOperator) and
                expression.operator == '`'):
            return FuncCall(expression.location, expression.mid,
                            [expression.lhs, expression.rhs])

        if (isinstance(expression, BinaryOperator) and
                expression.operator == '.'):
            # a.b first parses b as a variable lookup, and this fixes that
            # we can also have a.b() which parses b() as a function call
            # function calls can be nested, too
            rhs = expression.rhs
            calls = []      # innermost last
            while isinstance(rhs, FuncCall):
                calls.append(rhs)
                rhs = rhs.function

            if not isinstance(rhs, GetVar):
                raise common.CompileError("invalid attribute", rhs.location)

            # expression.location is the location of '.'
            result = GetAttr(
                expression.location + rhs.location,
                expression.lhs, rhs.varname)
            for call in reversed(calls):
                result = FuncCall(call.location, result, call.args)

            return result

        return expression

    def parse_expression(self, *, it_should_be='an expression'):
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
            raise common.CompileError(
                "should be %s" % it_should_be, not_expression.location)

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

                if kind & OperatorKind.TERNARY:
                    assert kind == OperatorKind.TERNARY     # no other flags

                    if not (index-1 >= 0 and
                            index+4 <= len(parts) and
                            parts[index-1][0] and
                            not parts[index][0] and
                            parts[index+1][0] and
                            not parts[index+2][0] and
                            parts[index+2][1].value == token.value and
                            parts[index+3][0]):
                        raise common.CompileError(
                            "should be: expression {0}expression{0} expression"
                            .format(token.value),
                            token.location)

                    start_index = index-1
                    end_index = index+4

                    lhs = parts[index-1][1]
                    assert token is parts[index][1]
                    mid = parts[index+1][1]
                    token2 = parts[index+2][1]
                    rhs = parts[index+3][1]

                    # taking just one of the operator tokens feels wrong,
                    # because the other operator token isn't taken
                    #
                    # taking both and the mid expression between them feels
                    # wrong, because why aren't lhs and rhs taken
                    #
                    # taking everything feels about right
                    location = lhs.location + rhs.location

                    result = TernaryOperator(
                        location, token.value, lhs, mid, rhs)

                else:
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
                        result = PrefixOperator(
                            token.location, token.value, after)
                    elif before is not None and after is not None:
                        valid = bool(kind & OperatorKind.BINARY)
                        result = BinaryOperator(
                            token.location, token.value, before, after)
                    else:
                        valid = False
                        # result is not needed

                    if not valid:
                        raise common.CompileError(
                            "'%s' cannot be used like this" % token.value,
                            token.location)

                    start_index = index if before is None else index-1
                    end_index = index + 1 if after is None else index + 2

                result = self.operator_helper(result)

                assert start_index >= 0
                assert end_index <= len(parts)
                parts[start_index:end_index] = [(True, result)]

        assert len(parts) == 1
        result_is_expression, result = parts[0]
        assert result_is_expression
        return result

    def parse_generic_type_name(self):
        id_token = self.tokens.next_token()
        if id_token.type != 'ID':
            raise common.CompileError(
                "should be a name of a generic type", id_token.location)
        return (id_token.value, id_token.location)

    def parse_1line_statement(self, *, it_should_be='a one-line statement'):
        if self.tokens.peek().value == 'void':
            return VoidStatement(self.tokens.next_token().location)

        if self.tokens.peek().value == 'return':
            return_keyword = self.tokens.next_token()
            if self.tokens.eof() or self.tokens.peek().type == 'NEWLINE':
                value = None
                location = return_keyword.location
            else:
                value = self.parse_expression()
                location = return_keyword.location + value.location

            return Return(location, value)

        if self.tokens.peek().value == 'yield':
            yield_keyword = self.tokens.next_token()
            value = self.parse_expression()
            return Yield(yield_keyword.location + value.location, value)

        if self.tokens.peek().value == 'let':
            let = self.tokens.next_token()

            varname_token = self.tokens.next_token()
            if varname_token.type != 'ID':
                raise common.CompileError(
                    "invalid variable name", varname_token.location)

            if self.tokens.peek().value == '[':
                lbracket, generics, rbracket = self.parse_commasep_in_parens(
                    self.parse_generic_type_name, parens='[]',
                    allow_empty=False)
                _duplicate_check(generics, "generic type")
            else:
                generics = None

            eq = self.tokens.next_token()
            if eq.value != '=':
                raise common.CompileError("should be '='", eq.location)

            value = self.parse_expression()

            return Let(let.location, varname_token.value, generics, value,
                       export=False)

        if self.tokens.peek().value == 'export':
            export_token = self.tokens.next_token()
            if self.tokens.peek().value != 'let':
                raise common.CompileError(
                    "should be 'let'", self.tokens.peek().location)

            let = self.parse_1line_statement()
            assert isinstance(let, Let)
            return let._replace(export=True)

        if self.tokens.peek().value == 'import':
            import_token = self.tokens.next_token()

            string_token = self.tokens.next_token()
            if string_token.type != 'STRING':
                raise common.CompileError(
                    "should be a string", string_token.location)
            import_path_parts = self._handle_string_literal(
                string_token.value, string_token.location,
                allow_curly_braces=False)
            import_path_string = ''.join(
                part.python_string for part in import_path_parts)

            relative2 = self.compilation.source_path.parent
            import_path = relative2 / import_path_string.replace('/', os.sep)
            self.import_paths.append(import_path)

            as_ = self.tokens.next_token()
            if as_.value != 'as':
                raise common.CompileError("should be 'as'", as_.location)

            varname_token = self.tokens.next_token()
            if varname_token.type != 'ID':
                raise common.CompileError(
                    "should be a variable name", varname_token.location)

            return Import(import_token.location, import_path,
                          varname_token.value)

        result = self.parse_expression(it_should_be=it_should_be)

        if self.tokens.eof() or self.tokens.peek().value != '=':
            return result

        if not isinstance(result, GetVar):
            raise common.CompileError(
                "invalid assignment", self.tokens.peek().location)

        equal_sign = self.tokens.next_token()
        value = self.parse_expression()
        return SetVar(equal_sign.location, result.varname, value)

    def consume_semicolon_token(self):
        token = self.tokens.next_token()
        if token.value != ';':
            raise common.CompileError("should be ';'", token.location)

    def parse_statement(self):
        if self.tokens.peek().value == 'while':
            while_location = self.tokens.next_token().location
            condition = self.parse_expression()
            body = self.parse_block(consume_newline=True)
            return While(while_location, condition, body)

        if self.tokens.peek().value == 'if':
            if_location = self.tokens.next_token().location
            ifs = [(self.parse_expression(),
                    self.parse_block(consume_newline=True))]

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

        if self.tokens.peek().value == 'for':
            for_location = self.tokens.next_token().location
            init = self.parse_1line_statement()
            self.consume_semicolon_token()
            cond = self.parse_expression()
            self.consume_semicolon_token()
            incr = self.parse_1line_statement()
            body = self.parse_block(consume_newline=True)
            return For(for_location, init, cond, incr, body)

        result = self.parse_1line_statement(it_should_be='a statement')

        newline = self.tokens.next_token()
        if newline.type != 'NEWLINE':
            raise common.CompileError("should be a newline", newline.location)
        return result

    def parse_block(self, *, consume_newline=False):
        indent = self.tokens.next_token()
        if indent.type != 'INDENT':
            # there was no colon, tokenizer replaces 'colon indent' with
            # just 'indent' to make parsing a bit simpler
            raise common.CompileError("should be ':'", indent.location)

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
        while not self.tokens.eof():
            yield self.parse_statement()


def parse(compilation, code):
    parser = _AsdaParser(compilation, tokenizer.tokenize(compilation, code))
    statements = list(parser.parse_statements())    # must not be lazy iterator
    return (statements, parser.import_paths)
