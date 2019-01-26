import collections
import functools
import itertools

import more_itertools

from . import common, string_parser, tokenizer


def _astclass(name, fields):
    return collections.namedtuple(name, ['location'] + fields)


Integer = _astclass('Integer', ['python_int'])
String = _astclass('String', ['python_string'])
StrJoin = _astclass('StrJoin', ['parts'])
Let = _astclass('Let', ['varname', 'value'])
SetVar = _astclass('SetVar', ['varname', 'value'])
GetVar = _astclass('GetVar', ['varname'])
GetAttr = _astclass('GetAttr', ['obj', 'attrname'])
GetType = _astclass('GetType', ['name'])
# FromGeneric represents looking up a generic function or generic type
FromGeneric = _astclass('TypeFromGeneric', ['name', 'types'])
FuncCall = _astclass('FuncCall', ['function', 'args'])
# generics is a list of (typename, location) pairs, or None
FuncDefinition = _astclass('FuncDefinition', [
    'funcname', 'generics', 'args', 'returntype', 'body'])
Return = _astclass('Return', ['value'])
Yield = _astclass('Yield', ['value'])
VoidStatement = _astclass('VoidStatement', [])
# ifs is a list of (condition, body) pairs, where body is a list
If = _astclass('If', ['ifs', 'else_body'])
While = _astclass('While', ['condition', 'body'])
For = _astclass('For', ['init', 'cond', 'incr', 'body'])


class _TokenIterator:

    def __init__(self, token_iterable):
        self._iterator = iter(token_iterable)

    def copy(self):
        self._iterator, copied = itertools.tee(self._iterator)
        return _TokenIterator(copied)

    def _check_token(self, token, kind, value):
        error = functools.partial(common.CompileError, location=token.location)
        if value is not None and token.value != value:
            raise error("expected %r, got %r" % (value, token.value))
        if kind is not None and token.kind != kind:
            raise error("expected %s, got %r" % (kind, token.value))

    def coming_up(self, kind=None, value=None):
        try:
            token = next(self.copy()._iterator)
        except StopIteration:
            # end of file before the token
            return False

        try:
            self._check_token(token, kind, value)
        except common.CompileError:
            return False
        return True

    def next_token(self, required_kind=None, required_value=None):
        try:
            result = next(self._iterator)
        except StopIteration as e:      # pragma: no cover
            # this shouldn't happen if the asda code is invalid, because the
            # tokenizer puts a newline token at the end anyway and this should
            # get that and fail at _check_token() instead
            #
            # not-very-latest pythons suppress StopIteration if raised in
            # generator function, so make sure to be explicit
            raise RuntimeError("there's a bug in asdac") from e
        self._check_token(result, required_kind, required_value)
        return result

    def eof(self):
        try:
            next(self.copy()._iterator)
            return False
        except StopIteration:
            return True


def _duplicate_check(iterable, what_are_they):
    seen = set()
    for name, location in iterable:
        if name in seen:
            raise common.CompileError(
                "repeated %s name: %s" % (what_are_they, name), location)
        seen.add(name)


# asda integers must fit in 64 bits
INT64_MIN = -2**63
INT64_MAX = 2**63 - 1


def _to_string(parsed):
    location = parsed.location      # because pep8 line length
    return FuncCall(location, GetAttr(location, parsed, 'to_string'), [])


class _Parser:

    def __init__(self, tokens):
        assert isinstance(tokens, _TokenIterator)
        self.tokens = tokens

    def _handle_string_literal(self, string, location):
        assert len(string) >= 2 and string[0] == '"' and string[-1] == '"'
        content = string[1:-1]
        content_location = common.Location(
            location.filename, location.startline, location.startcolumn + 1,
            location.endline, location.endcolumn - 1)

        parts = []
        for kind, value, part_location in string_parser.parse(
                content, content_location):
            if kind == 'string':
                parts.append(String(part_location, value))

            elif kind == 'code':
                tokens = tokenizer.tokenize(
                    part_location.filename, value,
                    initial_lineno=part_location.startline,
                    initial_column=part_location.startcolumn)

                # make sure that there are some tokens, otherwise a thing in
                # _TokenIterator fails
                #
                # the parse() function at end of this file does that too,
                # because it does nothing if there are no tokens
                spyed, tokens = more_itertools.spy(tokens)
                if not spyed:
                    raise common.CompileError(
                        "you must put some code between { and }",
                        part_location)

                parser = _Parser(_TokenIterator(tokens))
                parts.append(_to_string(parser.parse_expression()))
                parser.tokens.next_token('newline')    # added by tokenizer
                assert parser.tokens.eof()   # if fails, string isn't one-line

            else:   # pragma: no cover
                raise NotImplementedError(kind)

        if len(parts) == 0:     # empty string
            return String(location, '')
        elif len(parts) == 1:
            # _replace is a documented namedtuple method
            # it has an underscore to allow creating a namedtuple with a field
            # called replace
            return parts[0]._replace(location=location)
        else:
            return StrJoin(location, parts)

    def _from_generic(self, name_token):
        self.tokens.next_token('op', '[')
        types, closing_bracket = self.parse_commasep_list(
            self.parse_type, ']', False)
        return FromGeneric(
            name_token.location + closing_bracket.location,
            name_token.value, types)

    def parse_expression(self):
        first_token = self.tokens.next_token()
        if first_token.kind == 'integer':
            value = int(first_token.value)
            if value < INT64_MIN:
                raise common.CompileError(
                    "this integer is too small", first_token.location)
            if value > INT64_MAX:
                raise common.CompileError(
                    "this integer is too big", first_token.location)
            result = Integer(first_token.location, int(first_token.value))
        elif first_token.kind == 'id':
            if self.tokens.coming_up('op', '['):
                result = self._from_generic(first_token)
            else:
                result = GetVar(first_token.location, first_token.value)
        elif first_token.kind == 'string':
            result = self._handle_string_literal(
                first_token.value, first_token.location)
        else:
            raise common.CompileError(
                "expected an expression, got %r" % first_token.value,
                first_token.location)

        while True:
            if self.tokens.coming_up('op', '.'):
                self.tokens.next_token('op', '.')
                attribute = self.tokens.next_token('id')
                result = GetAttr(result.location + attribute.location,
                                 result, attribute.value)
            elif self.tokens.coming_up('op', '('):
                self.tokens.next_token('op', '(')
                args, last_paren = self.parse_commasep_list(
                    self.parse_expression, ')', True)
                result = FuncCall(first_token.location + last_paren.location,
                                  result, args)
            else:
                break

        return result

    def parse_commasep_list(self, parse_callback, end_op, allow_empty):
        if self.tokens.coming_up('op', end_op):
            if not allow_empty:
                raise common.CompileError(
                    "expected 1 or more comma-separated items, got 0",
                    self.tokens.next_token('op', end_op).location)
            result = []
        else:
            result = [parse_callback()]
            while self.tokens.coming_up('op', ','):
                self.tokens.next_token('op', ',')
                result.append(parse_callback())
            # TODO: allow a trailing comma?

        return (result, self.tokens.next_token('op', end_op))

    def parse_let_statement(self):
        let = self.tokens.next_token('keyword', 'let')
        varname = self.tokens.next_token('id')
        self.tokens.next_token('op', '=')
        value = self.parse_expression()
        return Let(let.location + value.location, varname.value, value)

    def parse_block(self):
        self.tokens.next_token('indent')

        body = []
        while not self.tokens.coming_up('dedent'):
            body.append(self.parse_statement())

        self.tokens.next_token('dedent')
        return body

    def parse_if_statement(self):
        self.tokens.next_token('keyword', 'if')
        condition = self.parse_expression()
        body = self.parse_block()
        ifs = [(condition, body)]

        while self.tokens.coming_up('keyword', 'elif'):
            self.tokens.next_token('keyword', 'elif')

            # python evaluates tuple elements in order
            ifs.append((self.parse_expression(), self.parse_block()))

        if self.tokens.coming_up('keyword', 'else'):
            self.tokens.next_token('keyword', 'else')
            else_body = self.parse_block()
        else:
            else_body = []

        # using condition.location is not ideal, but not used in many places
        return If(condition.location, ifs, else_body)

    def parse_while(self):
        while_keyword = self.tokens.next_token('keyword', 'while')
        condition = self.parse_expression()
        body = self.parse_block()
        return While(
            while_keyword.location + condition.location, condition, body)

    # for init; cond; incr:
    #     body
    def parse_for(self):
        for_keyword = self.tokens.next_token('keyword', 'for')
        init = self.parse_statement(allow_multiline=False)
        self.tokens.next_token('op', ';')
        cond = self.parse_expression()
        self.tokens.next_token('op', ';')
        incr = self.parse_statement(allow_multiline=False)
        body = self.parse_block()
        return For(for_keyword.location + incr.location,
                   init, cond, incr, body)

    # TODO: update this when not all type names are id tokens
    def parse_type(self):
        first_token = self.tokens.next_token('id')
        if self.tokens.coming_up('op', '['):
            result = self._from_generic(first_token)
        else:
            result = GetType(first_token.location, first_token.value)
        return result

    def parse_arg_spec(self):
        tybe = self.parse_type()
        varname = self.tokens.next_token('id')
        return (tybe, varname.value, varname.location)

    # go_all_the_way=False is used when checking whether a valid-seeming
    # function definition is coming up
    def parse_func_definition(self):
        self.tokens.next_token('keyword', 'func')
        name = self.tokens.next_token('id')

        if self.tokens.coming_up('op', '['):
            def parse_a_generic():
                token = self.tokens.next_token('id')
                return (token.value, token.location)

            self.tokens.next_token('op', '[')
            generics, closing_bracket = self.parse_commasep_list(
                parse_a_generic, ']', False)
            _duplicate_check(generics, "generic type")

        else:
            generics = None

        self.tokens.next_token('op', '(')
        args, close_paren = self.parse_commasep_list(
            self.parse_arg_spec, ')', True)
        _duplicate_check(((arg[1], arg[2]) for arg in args), "argument")

        self.tokens.next_token('op', '->')

        if self.tokens.coming_up('keyword', 'void'):
            returntype = None
            type_location = self.tokens.next_token('keyword', 'void').location
        else:
            returntype = self.parse_type()
            type_location = returntype.location

        body = _Parser(self.tokens).parse_block()

        # the location of a function definition is just the first line,
        # because the body can get quite long
        location = type_location + close_paren.location
        return FuncDefinition(location, name.value, generics, args,
                              returntype, body)

    def parse_return(self):
        return_keyword = self.tokens.next_token('keyword', 'return')
        if self.tokens.coming_up('newline'):
            value = None
            location = return_keyword.location
        else:
            value = self.parse_expression()
            location = return_keyword.location + value.location
        return Return(location, value)

    def parse_yield(self):
        yield_keyword = self.tokens.next_token('keyword', 'yield')
        value = self.parse_expression()
        return Yield(yield_keyword.location + value.location, value)

    def parse_void_statement(self):
        void = self.tokens.next_token('keyword', 'void')
        return VoidStatement(void.location)

    def parse_statement(self, *, allow_multiline=True):
        if self.tokens.coming_up('keyword', 'if'):
            result = self.parse_if_statement()
            is_multiline = True

        elif self.tokens.coming_up('keyword', 'while'):
            result = self.parse_while()
            is_multiline = True

        elif self.tokens.coming_up('keyword', 'for'):
            result = self.parse_for()
            is_multiline = True

        elif self.tokens.coming_up('keyword', 'func'):
            result = self.parse_func_definition()
            is_multiline = True

        elif self.tokens.coming_up('keyword', 'let'):
            result = self.parse_let_statement()
            is_multiline = False

        elif self.tokens.coming_up('keyword', 'return'):
            result = self.parse_return()
            is_multiline = False

        elif self.tokens.coming_up('keyword', 'yield'):
            result = self.parse_yield()
            is_multiline = False

        elif self.tokens.coming_up('keyword', 'void'):
            result = self.parse_void_statement()
            is_multiline = False

        else:
            is_multiline = False

            first_expr = self.parse_expression()
            if self.tokens.coming_up('op', '='):
                if not isinstance(first_expr, GetVar):
                    raise common.CompileError(
                        "expected a variable", first_expr.location)
                self.tokens.next_token('op', '=')
                value = self.parse_expression()
                result = SetVar(first_expr.location + value.location,
                                first_expr.varname, value)

            elif isinstance(first_expr, FuncCall):
                result = first_expr

            else:
                raise common.CompileError(
                    "expected a let, a variable assignment, an if, a while, "
                    "a for, a return, a yield, a function definition or a "
                    "function call",
                    first_expr.location)

        if is_multiline:
            if not allow_multiline:
                raise common.CompileError(
                    "expected a one-line statement", result.location)
            # whatever gave the result has already handled the newline
        else:
            if allow_multiline:
                self.tokens.next_token('newline')

        return result


# this does the tokenizing because string formatting things need to invoke the
# tokenizer anyway
def parse(filename, code):
    parser = _Parser(_TokenIterator(tokenizer.tokenize(filename, code)))
    while not parser.tokens.eof():
        yield parser.parse_statement()
