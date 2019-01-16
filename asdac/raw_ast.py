import collections
import functools
import itertools

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
FuncFromGeneric = _astclass('FuncFromGeneric', ['funcname', 'types'])
FuncCall = _astclass('FuncCall', ['function', 'args'])
FuncDefinition = _astclass('FuncDefinition', [
    'funcname', 'is_generator', 'args', 'return_or_yield_type', 'body'])
Return = _astclass('Return', ['value'])
Yield = _astclass('Yield', ['value'])
If = _astclass('If', ['condition', 'if_body', 'else_body'])
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

    def coming_up(self, kind=None, value=None, *, how_soon=0):
        token = more_itertools.nth(self.copy()._iterator, how_soon)
        if token is None:
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
        except StopIteration as e:
            # not-very-latest pythons suppress StopIteration if raised in
            # generator function
            # TODO: raise CompileError instead with some nice location
            raise EOFError from e
        self._check_token(result, required_kind, required_value)
        return result

    def eof(self):
        try:
            next(self.copy()._iterator)
            return False
        except StopIteration:
            return True


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
            if self.tokens.coming_up('op', '['):
                # generic_func_name[T1, T2, ...]
                self.tokens.next_token('op', '[')
                types = self.parse_commasep_list(self.parse_type)
                closing_bracket = self.tokens.next_token('op', ']')
                result = FuncFromGeneric(
                    first_token.location + closing_bracket.location,
                    first_token.value, types)
            else:
                result = GetVar(first_token.location, first_token.value)
        elif first_token.kind == 'string':
            result = String(first_token.location, first_token.value.strip('"'))
        else:
            raise common.CompileError(
                "expected an expression, got %r" % first_token.value,
                first_token.location)

        while True:
            if self.tokens.coming_up('op', '.'):
                # rest of the code doesn't support the attributes, but this
                # code worked when i wrote it
                self.tokens.next_token('op', '.')
                attribute = self.tokens.next_token('id')
                result = GetAttr(result.location + attribute.location,
                                 result, attribute.value)
            elif self.tokens.coming_up('op', '('):
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
        return Let(let.location + value.location, varname.value, value)

    def parse_block(self):
        self.tokens.next_token('indent')

        body = []
        while not self.tokens.coming_up('dedent'):
            body.append(self.parse_statement())

        self.tokens.next_token('dedent')
        return body

    # TODO: elif
    def parse_if_statement(self):
        if_keyword = self.tokens.next_token('keyword', 'if')
        condition = self.parse_expression()
        if_body = self.parse_block()
        if self.tokens.coming_up('keyword', 'else'):
            self.tokens.next_token('keyword', 'else')
            else_body = self.parse_block()
        else:
            else_body = []
        return If(if_keyword.location + condition.location, condition,
                  if_body, else_body)

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
        typename = self.tokens.next_token('id')
        return (typename.value, typename.location)

    def parse_arg_spec(self):
        # TODO: update this when not all type names are id tokens
        typeinfo = self.parse_type()
        varname = self.tokens.next_token('id')
        return typeinfo + (varname.value, varname.location)

    def func_definition_coming_up(self):
        # first 'id' is a type name
        if not (self.tokens.coming_up('id') or
                self.tokens.coming_up('keyword', 'void')):
            return False

        # currently the 'generator' keyword can only be used for this
        if self.tokens.coming_up('keyword', 'generator', how_soon=1):
            return True

        # check for: TYPENAME FUNCNAME(...
        return (self.tokens.coming_up('id', how_soon=1) and
                self.tokens.coming_up('op', '(', how_soon=2))

    def parse_func_definition(self):
        if self.tokens.coming_up('keyword', 'void'):
            return_or_yield_type = None
            type_location = self.tokens.next_token('keyword', 'void').location
        else:
            return_or_yield_type, type_location = self.parse_type()

        if self.tokens.coming_up('keyword', 'generator'):
            generator_word = self.tokens.next_token('keyword', 'generator')
            if return_or_yield_type is None:
                raise common.CompileError(
                    "cannot create a void generator function",
                    type_location + generator_word.location)
            generator = True
        else:
            generator = False

        name = self.tokens.next_token('id')
        self.tokens.next_token('op', '(')
        args = self.parse_commasep_list(self.parse_arg_spec)
        close_paren = self.tokens.next_token('op', ')')

        body = _Parser(self.tokens).parse_block()

        # the location of a function definition is just the first line,
        # because the body can get quite long
        location = type_location + close_paren.location
        return FuncDefinition(location, name.value, generator, args,
                              return_or_yield_type, body)

    def parse_assignment(self):
        name = self.tokens.next_token('id')
        self.tokens.next_token('op', '=')
        value = self.parse_expression()
        return SetVar(name.location + value.location, name.value, value)

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
        location = yield_keyword.location + value.location
        return Yield(location, value)

    def parse_statement(self, *, allow_multiline=True):
        if self.tokens.coming_up('keyword', 'let'):
            result = self.parse_let_statement()
            is_multiline = False

        elif (self.tokens.coming_up('id') and
              self.tokens.coming_up('op', '=', how_soon=1)):
            result = self.parse_assignment()
            is_multiline = False

        elif self.tokens.coming_up('keyword', 'if'):
            result = self.parse_if_statement()
            is_multiline = True

        elif self.tokens.coming_up('keyword', 'while'):
            result = self.parse_while()
            is_multiline = True

        elif self.tokens.coming_up('keyword', 'for'):
            result = self.parse_for()
            is_multiline = True

        elif self.func_definition_coming_up():
            result = self.parse_func_definition()
            is_multiline = True

        elif self.tokens.coming_up('keyword', 'return'):
            result = self.parse_return()
            is_multiline = False

        elif self.tokens.coming_up('keyword', 'yield'):
            result = self.parse_yield()
            is_multiline = False

        else:
            # function call statement
            result = self.parse_expression()
            if not isinstance(result, FuncCall):
                raise common.CompileError(
                    "expected a let, a variable assignment, an if, a while, "
                    "a function definition or a function call",
                    result.location)
            is_multiline = False

        if is_multiline:
            if not allow_multiline:
                raise common.CompileError(
                    "expected a one-line statement", result.location)
            # whatever gave the result has already handled the newline
        else:
            if allow_multiline:
                self.tokens.next_token('newline')

        return result


def parse(tokens):
    token_iter = _TokenIterator(tokens)
    parser = _Parser(token_iter)
    while not token_iter.eof():
        yield parser.parse_statement()
