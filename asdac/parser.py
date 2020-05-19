import itertools
import typing

from asdac import ast, precedence, string_parser
from asdac.common import Compilation, CompileError, Location
from asdac.objects import BUILTIN_TYPES
from asdac.tokenizer import Token, tokenize


def _to_string(parsed: ast.Expression) -> ast.Expression:
    raise NotImplementedError
#    location = parsed.location      # because pep8 line length
#    return CallFunction(location, GetAttr(location, parsed, 'to_string'), [])


class _TokenIterator:

    def __init__(self, iterable: typing.Iterable[Token]):
        self._iterator = iter(iterable)

    def copy(self) -> '_TokenIterator':
        self._iterator, copy = itertools.tee(self._iterator)
        return _TokenIterator(copy)

    def peek(self) -> Token:
        return self.copy().next_token()

    def next_token(self) -> Token:
        try:
            return next(self._iterator)
        except StopIteration:
            # i think this code is currently impossible to reach, but that may
            # change in the future without noticing it when writing the
            # changing code
            #
            # TODO: the 'file' in this error message is wrong for an error that
            #       comes from the {...} part of a string literal. Also, how to
            #       figure out what we should put for location?
            raise CompileError("unexpected end of file", None)

    def eof(self) -> bool:
        # old bug: don't use .next_token() or .peek() and catch CompileError,
        # because that also catches errors from tokenizer
        try:
            next(self.copy()._iterator)
            return False
        except StopIteration:
            return True


T = typing.TypeVar('T')


class _ParserBase:

    def __init__(self, compilation: Compilation, tokens: _TokenIterator):
        self.compilation = compilation
        self.tokens = tokens

    def parse_commasep_in_parens(
        self,
        item_callback: typing.Callable[[], T],
        *,
        parens: typing.Tuple[str, str] = ('(', ')'),
        allow_empty: bool = True,
    ) -> typing.Tuple[Token, typing.List[T], Token]:
        lparen_string, rparen_string = parens

        lparen = self.tokens.next_token()
        assert lparen.value == lparen_string    # should be checked by caller

        result: typing.List[T] = []

        # doesn't need an eof check because tokenizer matches parentheses
        # an eof error wouldn't matter anyway
        while self.tokens.peek().value != rparen_string:
            if result:
                comma = self.tokens.next_token()
                if comma.value != ',':
                    raise CompileError(
                        "should be ',' or '%s'" % rparen_string,
                        comma.location)

            result.append(item_callback())

        rparen = self.tokens.next_token()
        assert rparen.value == rparen_string

        if (not allow_empty) and (not result):
            raise CompileError(
                "you must put something between '%s' and '%s'" % (
                    lparen_string, rparen_string),
                lparen.location + rparen.location)

        return (lparen, result, rparen)

    def parse_type(self) -> ast.ParserType:
        # TODO: functype, something from module, generics
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise CompileError("invalid type", name.location)

        return ast.ParserType(name.location, name.value)


class _FileParser(_ParserBase):

    def _parse_argument_definition(self) -> ast.ParserFunctionHeaderArg:
        tybe = self.parse_type()
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise CompileError("invalid variable name", name.location)
        location = tybe.location + name.location
        return ast.ParserFunctionHeaderArg(location, tybe, name.value)

    def _parse_function_header(self) -> ast.ParserFunctionHeader:
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise CompileError("should be a function name", name.location)

        lparen, args, rparen = self.parse_commasep_in_parens(
            self._parse_argument_definition)

        arrow = self.tokens.next_token()
        if arrow.value != '->':
            raise CompileError("should be '->'", arrow.location)

        if self.tokens.peek().value == 'void':
            returntype = None
            self.tokens.next_token()    # skip void
        else:
            returntype = self.parse_type()

        return ast.ParserFunctionHeader(name.value, args, returntype)

    def _parse_func_definition(self) -> ast.FuncDefinition:
        function_keyword = self.tokens.next_token()
        if function_keyword.value != 'function':
            raise CompileError(
                "should be 'function'", function_keyword.location)

        header = self._parse_function_header()
        body_parser = _FunctionContentParser(self.compilation, self.tokens)
        return ast.FuncDefinition(
            function_keyword.location,
            parser_header=header,
            function=None,
            body=body_parser.parse_block(consume_newline=True))

    def parse_file(self) -> typing.Iterator[ast.FuncDefinition]:
        while not self.tokens.eof():
            yield self._parse_func_definition()


class _FunctionContentParser(_ParserBase):

    def _handle_string_literal(
        self,
        string: str,
        location: Location,
        allow_curly_braces: bool,
    ) -> typing.List[ast.Expression]:
        assert len(string) >= 2 and string[0] == '"' and string[-1] == '"'
        content = string[1:-1]
        content_location = Location(
            location.compilation, location.offset + 1, location.length - 2)

        parts: typing.List[ast.Expression] = []
        for kind, value, part_location in string_parser.parse(
                content, content_location):
            if kind == 'string':
                parts.append(ast.StrConstant(
                    part_location, BUILTIN_TYPES['Str'], value))

            elif kind == 'code':
                if not allow_curly_braces:
                    raise CompileError(
                        "cannot use {...} strings here", part_location)

                tokens = _TokenIterator(tokenize(
                    part_location.compilation, value,
                    initial_offset=part_location.offset))

                parser = _FunctionContentParser(self.compilation, tokens)

                if parser.tokens.eof():
                    raise CompileError(
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
                    raise CompileError(
                        "invalid syntax",
                        token_list[0].location + token_list[-2].location)

                parts.append(_to_string(expression))

            else:   # pragma: no cover
                raise NotImplementedError(kind)

        return parts

    def operator_from_precedence_list_coming_up(self) -> bool:
        if self.tokens.eof():
            return False

        for ops in precedence.PRECEDENCE_LIST:
            for op, flags in ops:
                if self.tokens.peek().value == op:
                    return True
        return False

    def expression_without_operators_coming_up(self) -> bool:
        # '(' could be a function or parentheses for predecence
        # both are expressions
        #
        # 'if' is a part of an if expression: 'if foo then bar else baz'
        # (doesn't conflict with if statements)
        if self.tokens.peek().value in {'(', 'if', 'new', 'this'}:
            return True

        if self.tokens.peek().type in {'INTEGER', 'STRING', 'ID',
                                       'MODULEFUL_ID'}:
            return True

        return False

    # remember to update expression_without_operators_coming_up()
    # whenever you change this method!
    def parse_expression_without_operators_or_calls(self) -> ast.Expression:
        if self.tokens.peek().type == 'ID':
            token = self.tokens.next_token()
            return ast.GetVar(
                location=token.location,
                type=None,
                var=None,
                parser_var=ast.ParserVariable(token.value))

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
                raise NotImplementedError("no lambda functions yet :(")

            else:
                # parentheses are being used for precedence here
                lparen = self.tokens.next_token()
                assert lparen.value == '('
                result = self.parse_expression()
                rparen = self.tokens.next_token()

                if rparen.value != ')':
                    raise CompileError("should be ')'", rparen.location)

                return result

        if self.tokens.peek().type == 'INTEGER':
            token = self.tokens.next_token()
            return ast.IntConstant(token.location, BUILTIN_TYPES['Int'],
                                   int(token.value))

        if self.tokens.peek().type == 'STRING':
            token = self.tokens.next_token()
            parts = self._handle_string_literal(
                token.value, token.location, allow_curly_braces=True)

            if len(parts) == 0:     # empty string
                return ast.StrConstant(
                    token.location, BUILTIN_TYPES['Str'], '')
            if len(parts) == 1:
                # replace location with token.location
                dynamically_typed_shit = parts[0].__dict__.copy()
                dynamically_typed_shit['location'] = token.location
                return type(parts[0])(**dynamically_typed_shit)
            return ast.StrJoin(token.location, BUILTIN_TYPES['Str'], parts)

        if self.tokens.peek().value == 'if':
            # if cond then true_expr else false_expr
            if_ = self.tokens.next_token()
            cond = self.parse_expression()

            then = self.tokens.next_token()
            if then.value != 'then':
                raise CompileError("should be 'then'", then.location)
            true_expr = self.parse_expression()

            elze = self.tokens.next_token()
            if elze.value != 'else':
                raise CompileError("should be 'else'", elze.location)
            false_expr = self.parse_expression()

            return ast.IfExpression(
                if_.location, None, cond, true_expr, false_expr)

        raise CompileError(
            "invalid expression", self.tokens.next_token().location)

    def _parse_function(
            self, expression: ast.Expression) -> ast.ParserFunctionRef:
        if not isinstance(expression, ast.GetVar):
            raise CompileError(
                "should be a function name", expression.location)

        return ast.ParserFunctionRef(expression.parser_var.name)

    def parse_expression_without_operators(self) -> ast.Expression:
        result = self.parse_expression_without_operators_or_calls()

        # this is part of parsing an expression because the list of function
        # arguments isn't a valid expression, so it's hard to do this with
        # operators
        #
        # TODO: add here something like this code when functions are objects:
        #   while (not self.tokens.eof()) and self.tokens.peek().value == '(':

        if (not self.tokens.eof()) and self.tokens.peek().value == '(':
            lparen, args, rparen = self.parse_commasep_in_parens(
                self.parse_expression)
            function = self._parse_function(result)
            result = ast.CallFunction(
                result.location + rparen.location, None,
                ast.ParserFunctionRef(function.name), None, args)

        return result

    def parse_expression(
        self,
        *,
        it_should_be: str = 'an expression',
    ) -> ast.Expression:
        parts: typing.List[typing.Union[ast.Expression, Token]] = []
        while True:
            expression_coming = self.expression_without_operators_coming_up()
            operator_coming = self.operator_from_precedence_list_coming_up()
            assert not (expression_coming and operator_coming)

            if expression_coming:
                parts.append(self.parse_expression_without_operators())
            elif operator_coming:
                parts.append(self.tokens.next_token())
            else:
                break

        if not parts:
            # next_token() may raise CompileError for end of file, that's fine
            not_expression = self.tokens.next_token()
            raise CompileError(
                "should be %s" % it_should_be, not_expression.location)

        return precedence.handle_precedence(parts)

    def parse_one_line_ish_statement(
        self,
        *,
        it_should_be: str = 'a one-line-ish statament',
    ) -> typing.List[ast.Statement]:
        if self.tokens.peek().value == 'void':
            self.tokens.next_token()
            return []

        if self.tokens.peek().value == 'return':
            return_keyword = self.tokens.next_token()
            if self.tokens.eof() or self.tokens.peek().type == 'NEWLINE':
                value = None
            else:
                value = self.parse_expression()

            return [ast.Return(return_keyword.location, value)]

        if self.tokens.peek().value == 'throw':
            return [ast.Throw(self.tokens.next_token().location)]

        if self.tokens.peek().value == 'let':
            # TODO: outer let, export let
            let_keyword = self.tokens.next_token()
            varname = self.tokens.next_token()
            if varname.type != 'ID':
                raise CompileError(
                    "should be a variable name", varname.location)

            equals_sign = self.tokens.next_token()
            if equals_sign.value != '=':
                raise CompileError("should be '='", equals_sign.location)

            initial_value = self.parse_expression()
            return [ast.Let(
                let_keyword.location, None, ast.ParserVariable(varname.value),
                initial_value)]

        result = self.parse_expression(it_should_be=it_should_be)

        if (not self.tokens.eof()) and self.tokens.peek().value == '=':
            equal_sign = self.tokens.next_token()
            value = self.parse_expression()

            if isinstance(result, ast.GetVar):
                return [ast.SetVar(
                    equal_sign.location, None, result.parser_var, value)]
            raise CompileError("can only assign to variables", result.location)

        if isinstance(result, ast.CallFunction):
            return [result]

        raise CompileError("invalid statement", result.location)

    def consume_semicolon_token(self) -> None:
        token = self.tokens.next_token()
        if token.value != ';':
            raise CompileError("should be ';'", token.location)

    def _parse_if_statement(self) -> ast.IfStatement:
        if_token = self.tokens.next_token()
        assert if_token.value in {'if', 'elif'}
        cond = self.parse_expression()
        if_body = self.parse_block(consume_newline=True)

        else_body: typing.List[ast.Statement] = []
        if not self.tokens.eof():
            if self.tokens.peek().value == 'elif':
                else_body = [self._parse_if_statement()]
            elif self.tokens.peek().value == 'else':
                self.tokens.next_token()
                else_body = self.parse_block(consume_newline=True)

        return ast.IfStatement(if_token.location, cond, if_body, else_body)

    def parse_statement(
        self,
        *,
        allow_classes: bool = False,
    ) -> typing.List[ast.Statement]:
        if self.tokens.peek().value == 'while':
            while_location = self.tokens.next_token().location
            cond = self.parse_expression()
            body = self.parse_block(consume_newline=True)
#            return Loop(
#                while_location, cond, BUILTIN_VARIABLES['True'], [], body)
            raise NotImplementedError

        # note that 'if x then y else z' is not a valid statement even though
        # it is a valid expression
        if self.tokens.peek().value == 'if':
            return [self._parse_if_statement()]

        if self.tokens.peek().value == 'do':
            do = self.tokens.next_token()
            body = self.parse_block(consume_newline=True)

            whale = self.tokens.next_token()
            if whale.value != 'while':
                raise CompileError("should be 'while'", whale.location)
            cond = self.parse_expression()

            newline = self.tokens.next_token()
            if newline.type != 'NEWLINE':
                raise CompileError(
                    "should be a newline", newline.location)

#            return Loop(
#                do.location, GetVar(BUILTIN_VARIABLES['True'], cond, [], body)
            raise NotImplementedError

        if self.tokens.peek().value == 'for':
            for_location = self.tokens.next_token().location
            init = self.parse_one_line_ish_statement()
            self.consume_semicolon_token()
            cond = self.parse_expression()
            self.consume_semicolon_token()
            incr = self.parse_one_line_ish_statement()
            body = self.parse_block(consume_newline=True)
            return init + [ast.Loop(for_location, cond, None, body, incr)]

        result = self.parse_one_line_ish_statement(it_should_be='a statement')

        newline = self.tokens.next_token()
        if newline.type != 'NEWLINE':
            raise CompileError("should be a newline", newline.location)

        return result

    def parse_block(
        self,
        *,
        consume_newline: bool = False,
    ) -> typing.List[ast.Statement]:
        indent = self.tokens.next_token()
        if indent.type != 'INDENT':
            # there was no colon, tokenizer replaces 'colon indent' with
            # just 'indent' to make parsing a bit simpler
            raise CompileError("should be ':'", indent.location)

        result = []
        while self.tokens.peek().type != 'DEDENT':
            result.extend(self.parse_statement())

        dedent = self.tokens.next_token()
        assert dedent.type == 'DEDENT'

        if consume_newline:
            newline = self.tokens.next_token()
            assert newline.type == 'NEWLINE', "tokenizer doesn't work"

        return result


def parse(
        compilation: Compilation,
        code: str) -> typing.List[ast.FuncDefinition]:
    tokens = list(tokenize(compilation, code))
    file_parser = _FileParser(compilation, _TokenIterator(tokens))
    return list(file_parser.parse_file())    # must not be lazy iterator
