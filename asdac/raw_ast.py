import collections
import functools
import itertools

import more_itertools
import sly

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
FromGeneric = _astclass('FromGeneric', ['name', 'types'])
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
PrefixOperator = _astclass('PrefixOperator', ['operator', 'expression'])
BinaryOperator = _astclass('BinaryOperator', ['operator', 'lhs', 'rhs'])


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
            location.filename, location.offset + 1, location.length - 2)

        parts = []
        for kind, value, part_location in string_parser.parse(
                content, content_location):
            if kind == 'string':
                parts.append(String(part_location, value))

            elif kind == 'code':
                tokens = tokenizer.tokenize(
                    part_location.filename, value,
                    initial_offset=part_location.offset)

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
                parser.tokens.next_token('NEWLINE')    # added by tokenizer
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
        self.tokens.next_token('OP', '[')
        types, closing_bracket = self.parse_commasep_list(
            self.parse_type, ']', False)
        return FromGeneric(
            name_token.location + closing_bracket.location,
            name_token.value, types)

    # see docs/syntax.md
    def parse_simple_expression(self):
        first_token = self.tokens.next_token()
        if first_token.kind == 'INTEGER':
            result = Integer(first_token.location, int(first_token.value))
        elif first_token.kind == 'ID':
            if self.tokens.coming_up('OP', '['):
                result = self._from_generic(first_token)
            else:
                result = GetVar(first_token.location, first_token.value)
        elif first_token.kind == 'STRING':
            result = self._handle_string_literal(
                first_token.value, first_token.location)
        elif first_token.kind == 'OP' and first_token.value == '(':
            result = self.parse_expression()
            self.tokens.next_token('OP', ')')
        else:
            raise common.CompileError(
                "expected an expression, got %r" % first_token.value,
                first_token.location)

        while True:
            if self.tokens.coming_up('OP', '.'):
                self.tokens.next_token('OP', '.')
                attribute = self.tokens.next_token('ID')
                result = GetAttr(result.location + attribute.location,
                                 result, attribute.value)
            elif self.tokens.coming_up('OP', '('):
                self.tokens.next_token('OP', '(')
                args, last_paren = self.parse_commasep_list(
                    self.parse_expression, ')', True)
                result = FuncCall(first_token.location + last_paren.location,
                                  result, args)
            else:
                break

        return result

    def parse_expression(self, *, allow_infix_syntax=True):
        operator_specs = [
            # these are (op_set, allow_chaining) tuples
            #
            # a OP b OP c is:
            #   * (a OP b) OP c, if allow_chaining is True
            #   * an error, if allow_chaining is False
            ({'*', '/'}, True),
            ({'+', '-'}, True),
            ({'==', '!='}, False),
        ]
        if allow_infix_syntax:
            operator_specs.append(({'`'}, True))

        # every other element of funny_stuff is an expression, every other is
        # (operator string, an operator token) or ('`', a function expression)
        # the second element of those is called "info" because i couldn't come
        # up with a better name
        funny_stuff = []

        # currently '-' is the only prefix operator
        if self.tokens.coming_up('OP', '-'):
            # make sure that e.g. -a-b and -a+b do the right thing
            funny_stuff.append(None)    # handled later
            funny_stuff.append(('-', self.tokens.next_token()))
        funny_stuff.append(self.parse_simple_expression())

        while any(self.tokens.coming_up('OP', op)
                  for op_set, allow_chaining in operator_specs
                  for op in op_set):
            token = self.tokens.next_token('OP')
            if token.value == '`':
                # infix syntax:  a `f` b  does the same thing as  f(a, b)
                funny_stuff.append(
                    ('`', self.parse_expression(allow_infix_syntax=False)))
                self.tokens.next_token('OP', '`')
            else:
                funny_stuff.append((token.value, token))

            funny_stuff.append(self.parse_simple_expression())

        # "merge" things together so that precedences are correct
        for op_set, allow_chaining in operator_specs:
            # find all places where those operators are
            indexes = [index - len(funny_stuff)     # relative to end
                       for index, value_and_info in enumerate(funny_stuff)
                       if index % 2 == 1 and value_and_info[0] in op_set]

            if not allow_chaining:
                for index1, index2 in zip(indexes, indexes[1:]):
                    if index1 + 2 == index2:
                        # the indexes are as next to each other as they can be
                        # i.e. there's 1 expression between them
                        # that's b in the below error message
                        op1, token1 = funny_stuff[index1]
                        op2, token2 = funny_stuff[index2]
                        raise common.CompileError(
                            "'a %s b %s c' is invalid syntax" % (op1, op2),
                            location=(token1.location + token2.location))

            # must go from beginning to end, because a+b+c means (a+b)+c
            # indexes start at end to avoid issues with them getting "outdated"
            for index in indexes:
                start = index-1
                # python's funny corner case: stuff[-1:0] != stuff[-1:]
                end = None if index+2 == 0 else index+2
                lhs, (op, info), rhs = funny_stuff[start:end]

                if lhs is None:     # the prefixing, see above
                    assert op == '-'
                    result = PrefixOperator(info.location + rhs.location,
                                            op, rhs)
                else:
                    location = lhs.location + rhs.location
                    if op == '`':
                        result = FuncCall(location, info, [lhs, rhs])
                    else:
                        result = BinaryOperator(location, op, lhs, rhs)

                funny_stuff[start:end] = [result]

        [result] = funny_stuff
        return result

    def parse_commasep_list(self, parse_callback, end_op, allow_empty):
        if self.tokens.coming_up('OP', end_op):
            if not allow_empty:
                raise common.CompileError(
                    "expected 1 or more comma-separated items, got 0",
                    self.tokens.next_token('OP', end_op).location)
            result = []
        else:
            result = [parse_callback()]
            while self.tokens.coming_up('OP', ','):
                self.tokens.next_token('OP', ',')
                result.append(parse_callback())
            # TODO: allow a trailing comma?

        return (result, self.tokens.next_token('OP', end_op))

    def parse_let_statement(self):
        let = self.tokens.next_token('KEYWORD', 'let')
        varname = self.tokens.next_token('ID')
        self.tokens.next_token('OP', '=')
        value = self.parse_expression()
        return Let(let.location + value.location, varname.value, value)

    def parse_block(self):
        self.tokens.next_token('INDENT')

        body = []
        while not self.tokens.coming_up('DEDENT'):
            body.append(self.parse_statement())

        self.tokens.next_token('DEDENT')
        return body

    def parse_if_statement(self):
        self.tokens.next_token('KEYWORD', 'if')
        condition = self.parse_expression()
        body = self.parse_block()
        ifs = [(condition, body)]

        while self.tokens.coming_up('KEYWORD', 'elif'):
            self.tokens.next_token('KEYWORD', 'elif')

            # python evaluates tuple elements in order
            ifs.append((self.parse_expression(), self.parse_block()))

        if self.tokens.coming_up('KEYWORD', 'else'):
            self.tokens.next_token('KEYWORD', 'else')
            else_body = self.parse_block()
        else:
            else_body = []

        # using condition.location is not ideal, but not used in many places
        return If(condition.location, ifs, else_body)

    def parse_while(self):
        while_keyword = self.tokens.next_token('KEYWORD', 'while')
        condition = self.parse_expression()
        body = self.parse_block()
        return While(
            while_keyword.location + condition.location, condition, body)

    # for init; cond; incr:
    #     body
    def parse_for(self):
        for_keyword = self.tokens.next_token('KEYWORD', 'for')
        init = self.parse_statement(allow_multiline=False)
        self.tokens.next_token('OP', ';')
        cond = self.parse_expression()
        self.tokens.next_token('OP', ';')
        incr = self.parse_statement(allow_multiline=False)
        body = self.parse_block()
        return For(for_keyword.location + incr.location,
                   init, cond, incr, body)

    # TODO: update this when not all type names are id tokens
    def parse_type(self):
        first_token = self.tokens.next_token('ID')
        if self.tokens.coming_up('OP', '['):
            result = self._from_generic(first_token)
        else:
            result = GetType(first_token.location, first_token.value)
        return result

    def parse_arg_spec(self):
        tybe = self.parse_type()
        varname = self.tokens.next_token('ID')
        return (tybe, varname.value, varname.location)

    def parse_func_definition(self):
        self.tokens.next_token('KEYWORD', 'func')
        name = self.tokens.next_token('ID')

        if self.tokens.coming_up('OP', '['):
            def parse_a_generic():
                token = self.tokens.next_token('ID')
                return (token.value, token.location)

            self.tokens.next_token('OP', '[')
            generics, closing_bracket = self.parse_commasep_list(
                parse_a_generic, ']', False)
            _duplicate_check(generics, "generic type")

        else:
            generics = None

        self.tokens.next_token('OP', '(')
        args, close_paren = self.parse_commasep_list(
            self.parse_arg_spec, ')', True)
        _duplicate_check(((arg[1], arg[2]) for arg in args), "argument")

        self.tokens.next_token('OP', '->')

        if self.tokens.coming_up('KEYWORD', 'void'):
            returntype = None
            type_location = self.tokens.next_token('KEYWORD', 'void').location
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
        return_keyword = self.tokens.next_token('KEYWORD', 'return')
        if self.tokens.coming_up('NEWLINE'):
            value = None
            location = return_keyword.location
        else:
            value = self.parse_expression()
            location = return_keyword.location + value.location
        return Return(location, value)

    def parse_yield(self):
        yield_keyword = self.tokens.next_token('KEYWORD', 'yield')
        value = self.parse_expression()
        return Yield(yield_keyword.location + value.location, value)

    def parse_void_statement(self):
        void = self.tokens.next_token('KEYWORD', 'void')
        return VoidStatement(void.location)

    def parse_statement(self, *, allow_multiline=True):
        if self.tokens.coming_up('KEYWORD', 'if'):
            result = self.parse_if_statement()
            is_multiline = True

        elif self.tokens.coming_up('KEYWORD', 'while'):
            result = self.parse_while()
            is_multiline = True

        elif self.tokens.coming_up('KEYWORD', 'for'):
            result = self.parse_for()
            is_multiline = True

        elif self.tokens.coming_up('KEYWORD', 'func'):
            result = self.parse_func_definition()
            is_multiline = True

        elif self.tokens.coming_up('KEYWORD', 'let'):
            result = self.parse_let_statement()
            is_multiline = False

        elif self.tokens.coming_up('KEYWORD', 'return'):
            result = self.parse_return()
            is_multiline = False

        elif self.tokens.coming_up('KEYWORD', 'yield'):
            result = self.parse_yield()
            is_multiline = False

        elif self.tokens.coming_up('KEYWORD', 'void'):
            result = self.parse_void_statement()
            is_multiline = False

        else:
            is_multiline = False

            first_expr = self.parse_expression()
            if self.tokens.coming_up('OP', '='):
                if not isinstance(first_expr, GetVar):
                    raise common.CompileError(
                        "expected a variable", first_expr.location)
                self.tokens.next_token('OP', '=')
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
                self.tokens.next_token('NEWLINE')

        return result


# this does the tokenizing because string formatting things need to invoke the
# tokenizer anyway
def parse(filename, code):
    parser = _Parser(_TokenIterator(tokenizer.tokenize(filename, code)))
    while not parser.tokens.eof():
        yield parser.parse_statement()
