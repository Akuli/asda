import collections
import functools

import more_itertools

from . import common


def _astclass(name, fields):
    return collections.namedtuple(name, ['location'] + fields)


Integer = _astclass('Integer', ['python_int'])
String = _astclass('String', ['python_string'])
Let = _astclass('Let', ['varname', 'value'])
SetVar = _astclass('SetVar', ['varname', 'value'])
GetVar = _astclass('GetVar', ['varname'])
GetAttr = _astclass('GetAttr', ['obj', 'attrname'])
FuncCall = _astclass('FuncCall', ['function', 'args'])
FuncDefinition = _astclass('FuncDefinition', ['funcname', 'args',
                                              'return_type', 'body'])
Return = _astclass('Return', ['value'])
If = _astclass('If', ['condition', 'if_body', 'else_body'])


class _TokenIterator:

    def __init__(self, token_iterable):
        # more_itertools.peekable is awesome
        self._iterator = more_itertools.peekable(token_iterable)

    def _check_token(self, token, kind, value):
        error = functools.partial(common.CompileError, location=token.location)
        if value is not None and token.value != value:
            raise error("expected %r, got %r" % (value, token.value))
        if kind is not None and token.kind != kind:
            raise error("expected %s, got %r" % (kind, token.value))

    def coming_up(self, kind=None, value=None, *, how_soon=1):
        head = self._iterator[:how_soon]
        if len(head) < how_soon:
            return False
        assert len(head) == how_soon

        try:
            self._check_token(head[-1], kind, value)
        except common.CompileError:
            return False
        return True

    def next_token(self, required_kind=None, required_value=None):
        result = next(self._iterator)
        self._check_token(result, required_kind, required_value)
        return result

    def eof(self):
        return (not self._iterator)


class _Parser:

    def __init__(self, tokens):
        self.tokens = tokens

    # be sure to change this if you change parse_expression!
    def expression_coming_up(self):
        return (self.tokens.coming_up('integer') or
                self.tokens.coming_up('id') or
                self.tokens.coming_up('string'))

    def parse_expression(self):
        first_token = self.tokens.next_token()
        if first_token.kind == 'integer':
            result = Integer(first_token.location, int(first_token.value))
        elif first_token.kind == 'id':
            result = GetVar(first_token.location, first_token.value)
        elif first_token.kind == 'string':
            result = String(first_token.location, first_token.value.strip('"'))
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
                # function call
                self.tokens.next_token('op', '(')
                args = self.parse_commasep_list(self.parse_expression)
                last_paren = self.tokens.next_token('op', ')')
                result = FuncCall(first_token.location + last_paren.location,
                                  result, args)
            else:
                break

        return result

    def parse_commasep_list(self, parse_callback):
        if not self.expression_coming_up():
            return []

        result = [parse_callback()]
        while self.tokens.coming_up('op', ','):
            self.tokens.next_token('op', ',')
            result.append(parse_callback())

        return result

    def parse_let_statement(self):
        let = self.tokens.next_token('keyword', 'let')
        varname = self.tokens.next_token('id')
        self.tokens.next_token('op', '=')
        value = self.parse_expression()
        self.tokens.next_token('newline')
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
        if_body = self.parse_block()

        if self.tokens.coming_up('keyword', 'else'):
            self.tokens.next_token('keyword', 'else')
            else_body = self.parse_block()
        else:
            else_body = []

        return If(condition, if_body, else_body)

    # TODO: update this when not all type names are id tokens
    def parse_type(self):
        typename = self.tokens.next_token('id')
        return (typename.value, typename.location)

    def parse_arg_spec(self):
        # TODO: update this when not all type names are id tokens
        typeinfo = self.parse_type()
        varname = self.tokens.next_token('id')
        return typeinfo + (varname.value, varname.location)

    def parse_func_definition(self):
        if self.tokens.coming_up('keyword', 'void'):
            return_type = None
            type_location = self.tokens.next_token('keyword', 'void').location
        else:
            return_type, type_location = self.parse_type()
        name = self.tokens.next_token('id')
        self.tokens.next_token('op', '(')
        args = self.parse_commasep_list(self.parse_arg_spec)
        close_paren = self.tokens.next_token('op', ')')

        body = _Parser(self.tokens).parse_block()

        # the location of a function definition is just the first line,
        # because the body can get quite long
        location = type_location + close_paren.location
        return FuncDefinition(location, name.value, args, return_type, body)

    def parse_assignment(self):
        name = self.tokens.next_token('id')
        self.tokens.next_token('op', '=')
        value = self.parse_expression()
        self.tokens.next_token('newline')
        return SetVar(name.location + value.location, name.value, value)

    def parse_return(self):
        return_keyword = self.tokens.next_token('keyword', 'return')
        if self.tokens.coming_up('newline'):
            value = None
            location = return_keyword.location
        else:
            value = self.parse_expression()
            location = return_keyword.location + value.location
        self.tokens.next_token('newline')
        return Return(location, value)

    def parse_statement(self):
        if self.tokens.coming_up('keyword', 'let'):
            return self.parse_let_statement()

        if (
          self.tokens.coming_up('id') and
          self.tokens.coming_up('op', '=', how_soon=2)):
            return self.parse_assignment()

        if self.tokens.coming_up('keyword', 'if'):
            return self.parse_if_statement()

        if (
                (self.tokens.coming_up('id') or
                 self.tokens.coming_up('keyword', 'void'))
                and self.tokens.coming_up('id', how_soon=2)
                and self.tokens.coming_up('op', '(', how_soon=3)):
            return self.parse_func_definition()

        if self.tokens.coming_up('keyword', 'return'):
            return self.parse_return()

        # function call statement
        result = self.parse_expression()
        if not isinstance(result, FuncCall):
            raise common.CompileError(
                "expected a let, a variable assignment, an if, a function "
                "definition or a function call", result.location)
        self.tokens.next_token('newline')
        return result


def parse(tokens):
    token_iter = _TokenIterator(tokens)
    parser = _Parser(token_iter)
    while not token_iter.eof():
        yield parser.parse_statement()
