import collections
import itertools
import os

from . import common, string_parser, tokenizer


def _astclass(name, fields):
    return collections.namedtuple(name, ['location'] + fields)


# the "header" of the function is the "(Blah b) -> Blah" part
# it is represented as (args, returntype) tuple
# args are (tybe, name, location) tuples
# returntype is None for "-> void"

# GetType's generics is a list of other GetTypes, or None
GetType = _astclass('GetType', ['name', 'generics'])
FuncType = _astclass('FuncType', ['header'])

Integer = _astclass('Integer', ['python_int'])
String = _astclass('String', ['python_string'])
StrJoin = _astclass('StrJoin', ['parts'])
# Let's generics is a list of (name, location) tuples, or None
Let = _astclass('Let', ['varname', 'generics', 'value', 'outer', 'export'])
GetVar = _astclass('GetVar', ['module_path', 'varname', 'generics'])
SetVar = _astclass('SetVar', ['varname', 'value'])
GetAttr = _astclass('GetAttr', ['obj', 'attrname'])
SetAttr = _astclass('SetAttr', ['obj', 'attrname', 'value'])
FuncCall = _astclass('FuncCall', ['function', 'args'])
FuncDefinition = _astclass('FuncDefinition', ['header', 'body'])
Return = _astclass('Return', ['value'])
Throw = _astclass('Throw', ['value'])
VoidStatement = _astclass('VoidStatement', [])
# IfStatement's ifs is a list of (cond, body) pairs, where body is a list
IfStatement = _astclass('IfStatement', ['ifs', 'else_body'])
IfExpression = _astclass('IfExpression', ['cond', 'true_expr', 'false_expr'])
While = _astclass('While', ['cond', 'body'])
DoWhile = _astclass('DoWhile', ['body', 'cond'])
For = _astclass('For', ['init', 'cond', 'incr', 'body'])
PrefixOperator = _astclass('PrefixOperator', ['operator', 'expression'])
BinaryOperator = _astclass('BinaryOperator', ['operator', 'lhs', 'rhs'])
TernaryOperator = _astclass('TernaryOperator', ['operator', 'lhs', 'mid',
                                                'rhs'])
# catches is a list of tuples:
#   (catch_location, errortype, varname, varname_location, body) tuples
Try = _astclass('TryCatch', ['try_body', 'catches',
                             'finally_location', 'finally_body'])
New = _astclass('New', ['tybe', 'args'])
# args are (tybe, name, location) tuples
# methods are (name, name_location, FuncDefinition) tuples
Class = _astclass('Class', ['name', 'args', 'methods'])
ThisExpression = _astclass('This', [])


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


# the values can be used as bit flags, e.g. OP_BINARY | OP_BINARY_CHAINING
#
# i would use enum.IntFlag but it's new in python 3.6, and other stuff works
# on python 3.5
OP_PREFIX = 1 << 0              # -x
OP_BINARY = 1 << 1              # x + y
OP_TERNARY = 1 << 2             # x `y` z
OP_BINARY_CHAINING = 1 << 3     # allow writing e.g. 'x + y + z'


_PRECEDENCE_LIST = [
    [('*', OP_BINARY | OP_BINARY_CHAINING)],
    [('+', OP_BINARY | OP_BINARY_CHAINING),
     ('-', (OP_PREFIX | OP_BINARY | OP_BINARY_CHAINING))],
    [('==', OP_BINARY),
     ('!=', OP_BINARY)],
    [('.', OP_BINARY | OP_BINARY_CHAINING)],
    [('`', OP_TERNARY)],
]


def _find_adjacent_items(the_list, key):
    for item1, item2 in zip(the_list, the_list[1:]):
        if key(item1, item2):
            return (item1, item2)
    return None


# value is an expression ast node or an operator token
_PrecedenceHandlerPart = collections.namedtuple(
    '_PrecedenceHandlerPart', ['is_expression', 'value'])


class _PrecedenceHandler:

    # parts should be a list of _PrecedenceHandlerPart
    def __init__(self, parts, part_parsed_callback):
        self.parts = parts.copy()
        self.part_parsed_callback = part_parsed_callback
        assert self.parts

    # there must not be two expressions next to each other without an
    # operator between
    def _check_no_adjacent_parts(self):
        adjacent_expression_parts = _find_adjacent_items(
            self.parts,
            lambda part1, part2: part1.is_expression and part2.is_expression
        )
        if adjacent_expression_parts is not None:
            part1, part2 = adjacent_expression_parts
            # if you have an idea for a better error message, add that here
            raise common.CompileError(
                "invalid syntax", part1.value.location + part2.value.location)

    def _find_op(self, op_flags_pairs):
        ops = [op for op, flags in op_flags_pairs]

        for parts_index, part in enumerate(self.parts):
            if part.is_expression:
                continue
            token = part.value

            try:
                op_index = ops.index(token.value)
            except ValueError:
                continue

            flags = op_flags_pairs[op_index][1]
            return (parts_index, flags, token)

        return None

    # the tokens around the token being considered are named like this:
    #   before, this_token, after, that_token, more_after
    #
    # _handle_blah() methods return tuples like this:
    #   (parts used before this_token, parts used after this_token, result)

    def _handle_ternary(self, before, this_token, after,
                        that_token, more_after):
        if (
          before is None or
          after is None or
          that_token is None or
          that_token.value != this_token.value or
          more_after is None):
            raise common.CompileError(
                "should be: expression {0}expression{0} expression"
                .format(this_token.value),
                this_token.location)

        # taking just one of the operator tokens feels wrong, because the other
        # operator token isn't taken
        #
        # taking both and the mid expression between them feels wrong, because
        # why aren't lhs and rhs taken
        #
        # taking everything feels about right
        location = before.location + more_after.location

        result = TernaryOperator(location, this_token.value, before, after,
                                 more_after)
        return (1, 3, result)

    def _binary_is_chained_but_shouldnt_be(
            self, that_token, other_op, other_flags):
        return bool(other_op == that_token.value and
                    (other_flags & OP_BINARY) and
                    not (other_flags & OP_BINARY_CHAINING))

    def _handle_binary_or_prefix(self, before, this_token, after, that_token,
                                 op_flags_pairs, flags):
        if before is None and after is not None and (flags & OP_PREFIX):
            result = PrefixOperator(
                this_token.location, this_token.value, after)
            return (0, 1, result)

        if before is not None and after is not None and (flags & OP_BINARY):
            if (
              that_token is not None and
              not (flags & OP_BINARY_CHAINING) and
              any(self._binary_is_chained_but_shouldnt_be(that_token, *pair)
                  for pair in op_flags_pairs)):
                raise common.CompileError(
                    "'a {0} b {1} c' is not valid syntax"
                    .format(this_token.value, that_token.value),
                    that_token.location)

            result = BinaryOperator(
                this_token.location, this_token.value, before, after)
            return (1, 1, result)

        raise common.CompileError(
            "'%s' cannot be used like this" % this_token.value,
            this_token.location)

    def _get_part_value(self, index, should_be_expression):
        return self.parts[index].value if (
            index >= 0 and
            index < len(self.parts) and
            self.parts[index].is_expression == should_be_expression
        ) else None

    def run(self):
        self._check_no_adjacent_parts()

        for op_flags_pairs in _PRECEDENCE_LIST:
            while True:
                find_result = self._find_op(op_flags_pairs)
                if find_result is None:
                    break
                index, flags, this_token = find_result

                before = self._get_part_value(index-1, True)
                after = self._get_part_value(index+1, True)
                that_token = self._get_part_value(index+2, False)
                more_after = self._get_part_value(index+3, True)

                if flags & OP_TERNARY:
                    assert flags == OP_TERNARY     # no other flags
                    before_count, after_count, result = self._handle_ternary(
                        before, this_token, after, that_token, more_after)
                else:
                    before_count, after_count, result = (
                        self._handle_binary_or_prefix(
                            before, this_token, after, that_token,
                            op_flags_pairs, flags))

                result = self.part_parsed_callback(result)

                start_index = index - before_count
                end_index = index + 1 + after_count
                assert start_index >= 0
                assert end_index <= len(self.parts)
                self.parts[start_index:end_index] = [
                    _PrecedenceHandlerPart(True, result)]

        assert len(self.parts) == 1
        assert self.parts[0].is_expression
        return self.parts[0].value


class _AsdaParser:

    def __init__(self, compilation, token_generator, import_paths):
        # order matters, because modules may have import time side-effects (ew)
        assert isinstance(import_paths, collections.OrderedDict)

        self.compilation = compilation
        self.tokens = _TokenIterator(token_generator)
        self.import_paths = import_paths

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

                parser = _AsdaParser(
                    self.compilation, tokens, self.import_paths)

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

    def parse_function_header(self, parse_an_arg):
        lparen, args, rparen = self.parse_commasep_in_parens(
            parse_an_arg)
        _duplicate_check((arg[1:] for arg in args), 'argument')

        arrow = self.tokens.next_token()
        if arrow.value != '->':
            raise common.CompileError("should be '->'", arrow.location)

        if self.tokens.peek().value == 'void':
            returntype = None
            location = (lparen.location +
                        self.tokens.next_token().location)
        else:
            returntype = self.parse_type()
            location = lparen.location + returntype.location

        return (location, args, returntype)

    def parse_type(self):
        name = self.tokens.next_token()
        if name.value == 'functype':
            lbracket = self.tokens.next_token()
            if lbracket.value != '{':
                raise common.CompileError("should be '{'", lbracket.location)

            header_location, *header = self.parse_function_header(
                self.parse_type)

            rbracket = self.tokens.next_token()
            if rbracket.value != '}':
                raise common.CompileError("should be '}'", rbracket.location)

            return FuncType(name.location + rbracket.location, tuple(header))

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

    def operator_from_precedence_list_coming_up(self):
        if self.tokens.eof():
            return False

        for ops in _PRECEDENCE_LIST:
            for op, precedence in ops:
                if self.tokens.peek().value == op:
                    return True
        return False

    def expression_without_operators_coming_up(self):
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

    def parse_argument_definition(self):
        tybe = self.parse_type()
        name = self.tokens.next_token()
        if name.type != 'ID':
            raise common.CompileError("invalid variable name", name.location)
        location = tybe.location + name.location
        return (tybe, name.value, location)

    # remember to update expression_without_operators_coming_up()
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
                location, *header = self.parse_function_header(
                    self.parse_argument_definition)
                body = self.parse_block()
                return FuncDefinition(location, tuple(header), body)

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

        if self.tokens.peek().type in {'ID', 'MODULEFUL_ID'}:
            token = self.tokens.next_token()

            # it's easier to do this here than to do it later
            if self.tokens.peek().value == '[':
                lbracket, generics, rbracket = self.parse_commasep_in_parens(
                    self.parse_type, parens='[]', allow_empty=False)
                location = token.location + rbracket.location
            else:
                generics = None
                location = token.location

            if token.type == 'MODULEFUL_ID':
                module, name = token.value.split(':')
                try:
                    module_path = self.import_paths[module]
                except KeyError as e:
                    raise common.CompileError(
                        "nothing has been imported as %s" % module) from e
            else:
                module_path = None
                name = token.value

            return GetVar(location, module_path, name, generics)

        if self.tokens.peek().value == 'this':
            return ThisExpression(self.tokens.next_token().location)

        if self.tokens.peek().value == 'if':
            # if cond then true_expr else false_expr
            if_ = self.tokens.next_token()
            cond = self.parse_expression()

            then = self.tokens.next_token()
            if then.value != 'then':
                raise common.CompileError("should be 'then'", then.location)
            true_expr = self.parse_expression()

            elze = self.tokens.next_token()
            if elze.value != 'else':
                raise common.CompileError("should be 'else'", elze.location)
            false_expr = self.parse_expression()

            return IfExpression(if_.location, cond, true_expr, false_expr)

        if self.tokens.peek().value == 'new':
            new = self.tokens.next_token()
            tybe = self.parse_type()
            lparen, args, rparen = self.parse_commasep_in_parens(
                self.parse_expression)
            return New(new.location, tybe, args)

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

            if (not isinstance(rhs, GetVar)) or rhs.module_path is not None:
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
                parts.append(_PrecedenceHandlerPart(
                    True, self.parse_expression_without_operators()))
            elif operator_coming:
                parts.append(_PrecedenceHandlerPart(
                    False, self.tokens.next_token()))
            else:
                break

        if not parts:
            # next_token() may raise CompileError for end of file, that's fine
            not_expression = self.tokens.next_token()
            raise common.CompileError(
                "should be %s" % it_should_be, not_expression.location)

        return _PrecedenceHandler(parts, self.operator_helper).run()

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
            else:
                value = self.parse_expression()

            return Return(return_keyword.location, value)

        if self.tokens.peek().value == 'throw':
            throw = self.tokens.next_token()
            value = self.parse_expression()
            return Throw(throw.location, value)

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
                       outer=False, export=False)

        if self.tokens.peek().value in {'outer', 'export'}:
            prefix_word = self.tokens.next_token().value
            if self.tokens.peek().value != 'let':
                raise common.CompileError(
                    "should be 'let'", self.tokens.peek().location)

            let = self.parse_1line_statement()
            assert isinstance(let, Let)
            return let._replace(**{prefix_word: True})

        if self.tokens.peek().value == 'import':
            raise common.CompileError(
                "cannot import here, only at beginning of file",
                self.tokens.peek().location)

        result = self.parse_expression(it_should_be=it_should_be)

        if (not self.tokens.eof()) and self.tokens.peek().value == '=':
            if not isinstance(result, (GetVar, GetAttr)):
                raise common.CompileError(
                    "invalid assignment", self.tokens.peek().location)

            equal_sign = self.tokens.next_token()
            value = self.parse_expression()

            if isinstance(result, GetVar):
                assert result.module_path is None, (
                    "can't assign to other modules yet")
                assert result.generics is None, (
                    "can't assign to generic variables yet")
                return SetVar(equal_sign.location, result.varname, value)

            if isinstance(result, GetAttr):
                return SetAttr(equal_sign.location, result.obj,
                               result.attrname, value)

            raise RuntimeError("wut")   # pragma: no cover

        if isinstance(result, FuncCall):
            return result

        raise common.CompileError("invalid statement", result.location)

    def parse_imports(self):
        while (not self.tokens.eof()) and self.tokens.peek().value == 'import':
            self.tokens.next_token()

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

            as_ = self.tokens.next_token()
            if as_.value != 'as':
                raise common.CompileError("should be 'as'", as_.location)

            varname_token = self.tokens.next_token()
            if varname_token.type != 'ID':
                raise common.CompileError(
                    "should be a valid module identifier name",
                    varname_token.location)

            if varname_token.value in self.import_paths:
                raise common.CompileError(
                    "there are multiple imports like 'import something as %s'"
                    % varname_token.value,
                    varname_token.location)

            newline = self.tokens.next_token()
            if newline.type != 'NEWLINE':
                raise common.CompileError("should be a newline character")

            self.import_paths[varname_token.value] = import_path

    def consume_semicolon_token(self):
        token = self.tokens.next_token()
        if token.value != ';':
            raise common.CompileError("should be ';'", token.location)

    def _parse_try_statement(self):
        try_location = self.tokens.next_token().location
        try_body = self.parse_block(consume_newline=True)

        catches = []
        while ((not self.tokens.eof()) and
               self.tokens.peek().value == 'catch'):
            catch = self.tokens.next_token()

            tybe = self.parse_type()
            if self.tokens.peek().type == 'ID':
                varname_token = self.tokens.next_token()
                if varname_token.type != 'ID':
                    raise common.Compilation("should be a variable name",
                                             varname_token.location)
                varname = varname_token.value
                varname_location = varname_token.location
            else:
                varname = None
                varname_location = None

            catch_body = self.parse_block(consume_newline=True)
            catches.append((catch.location, tybe, varname,
                            varname_location, catch_body))

        if ((not self.tokens.eof()) and
                self.tokens.peek().value == 'finally'):
            finally_location = self.tokens.next_token().location
            finally_body = self.parse_block(consume_newline=True)
        elif catches:
            finally_location = None
            finally_body = []
        else:
            raise common.CompileError(
                "you need to use 'catch' or 'finally' after a 'try'",
                try_location)

        return Try(try_location, try_body, catches,
                   finally_location, finally_body)

    def _parse_method(self):
        method = self.tokens.next_token()
        if method.value == 'void':
            newline = self.tokens.next_token()
            if newline.type != 'NEWLINE':
                raise common.CompileError("should be a newline",
                                          newline.location)
            return None

        if method.value != 'method':
            raise common.CompileError("should be 'method'", method.location)

        name = self.tokens.next_token()
        if name.type != 'ID':
            raise common.CompileError(
                "should be the name of the method", name.location)

        junky_location, *header = self.parse_function_header(
            self.parse_argument_definition)
        body = self.parse_block(consume_newline=True)
        return (name.value, name.location,
                FuncDefinition(method.location, tuple(header), body))

    # note that 'if x then y else z' is not a valid statement even though it
    # is a valid expression
    def parse_statement(self, *, allow_classes=False):
        if self.tokens.peek().value == 'while':
            while_location = self.tokens.next_token().location
            cond = self.parse_expression()
            body = self.parse_block(consume_newline=True)
            return While(while_location, cond, body)

        if self.tokens.peek().value == 'do':
            do = self.tokens.next_token()
            body = self.parse_block(consume_newline=True)

            whale = self.tokens.next_token()
            if whale.value != 'while':
                raise common.CompileError("should be 'while'", whale.location)
            cond = self.parse_expression()

            newline = self.tokens.next_token()
            if newline.type != 'NEWLINE':
                raise common.CompileError(
                    "should be a newline", newline.location)

            return DoWhile(do.location, body, cond)

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

            return IfStatement(if_location, ifs, else_body)

        if self.tokens.peek().value == 'for':
            for_location = self.tokens.next_token().location
            init = self.parse_1line_statement()
            self.consume_semicolon_token()
            cond = self.parse_expression()
            self.consume_semicolon_token()
            incr = self.parse_1line_statement()
            body = self.parse_block(consume_newline=True)
            return For(for_location, init, cond, incr, body)

        if self.tokens.peek().value == 'try':
            return self._parse_try_statement()

        if allow_classes and self.tokens.peek().value == 'class':
            class_location = self.tokens.next_token().location
            name = self.tokens.next_token()
            if name.type != 'ID':
                raise common.CompileError(
                    "should be the name of the class", name.location)

            lparen, args, rparen = self.parse_commasep_in_parens(
                self.parse_argument_definition)
            none_methods = self.parse_block(
                parse_content=self._parse_method, consume_newline=True)
            methods = [method for method in none_methods if method is not None]

            arg_infos = [arg[1:] for arg in args]
            method_infos = [method[:2] for method in methods]
            _duplicate_check(arg_infos, 'argument')
            _duplicate_check(method_infos, 'method')
            _duplicate_check(arg_infos + method_infos, 'argument or method')

            return Class(class_location + name.location,
                         name.value, args, methods)

        result = self.parse_1line_statement(it_should_be='a statement')

        newline = self.tokens.next_token()
        if newline.type != 'NEWLINE':
            raise common.CompileError("should be a newline", newline.location)
        return result

    def parse_block(self, *, parse_content=None, consume_newline=False):
        if parse_content is None:
            parse_content = self.parse_statement

        indent = self.tokens.next_token()
        if indent.type != 'INDENT':
            # there was no colon, tokenizer replaces 'colon indent' with
            # just 'indent' to make parsing a bit simpler
            raise common.CompileError("should be ':'", indent.location)

        result = []
        while self.tokens.peek().type != 'DEDENT':
            result.append(parse_content())

        dedent = self.tokens.next_token()
        assert dedent.type == 'DEDENT'

        if consume_newline:
            newline = self.tokens.next_token()
            assert newline.type == 'NEWLINE', "tokenizer doesn't work"

        return result

    def parse_file(self):
        while not self.tokens.eof():
            yield self.parse_statement(allow_classes=True)


def parse(compilation, code):
    parser = _AsdaParser(compilation, tokenizer.tokenize(compilation, code),
                         collections.OrderedDict())
    parser.parse_imports()
    statements = list(parser.parse_file())    # must not be lazy iterator
    return (statements, list(parser.import_paths.values()))
