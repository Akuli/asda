import collections
import functools

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


# i need to be able to parse an expression that can't be a statement
# currently the only way to implement that is to parse a statement and check
# whether that is an expression
# i wish sly's parsers supported inheritance so i could do this less shittily
_expression_classes = set()


def _expression_class(klass):
    _expression_classes.add(klass)
    return lambda func: func


class AsdaParser(sly.Parser):
    # shuts up flake8
    if False:
        _ = None

    tokens = tokenizer.AsdaLexer.tokens | tokenizer.AsdaLexer.literals - {':'}
    precedence = (
        ('left', '`'),   # yes, this works with just the first token type
        ('nonassoc', EQ, NE),   # noqa
        ('left', '+', '-'),
        ('left', '*'),
    )

    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.create_location = functools.partial(common.Location, filename)

    def error(self, token):
        assert token is not None
        location = common.Location(
            self.filename, token.index, len(token.value))
        raise common.CompileError("syntax error", location)

    @_expression_class(String)
    @_expression_class(StrJoin)
    def handle_string_literal(self, string, location):
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

                parser = AsdaParser(self.filename)
                parsed = parser.parse(tokens)
                try:
                    [expression] = parsed
                except ValueError:
                    if parsed:
                        wanted = "exactly 1 expression"
                    else:
                        wanted = "some code"
                    raise common.CompileError(
                        "you must put %s between { and }" % wanted,
                        part_location)

                assert isinstance(expression, tuple(_expression_classes))
                parts.append(_to_string(expression))

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

    # abstracts away a sly implementation detail
    def last_token_offset(self):
        return self.symstack[-1].index

    @_('statements statement')
    def statements(self, parsed):
        return parsed.statements + [parsed.statement]

    @_('')     # noqa
    def statements(self, parsed):
        return []

    @_('oneline_statement NEWLINE')
    def statement(self, parsed):
        return parsed.oneline_statement

    # types
    # ~~~~~

    @_('ID')
    def type(self, parsed):
        return GetType(self.create_location(parsed.index, len(parsed.ID)),
                       parsed.ID)

    @_('ID from_generic')     # noqa
    def type(self, parsed):
        types, end_offset = parsed.from_generic
        return FromGeneric(
            self.create_location(parsed.index, end_offset - parsed.index),
            parsed.ID, types)

    # control flow statements
    # ~~~~~~~~~~~~~~~~~~~~~~~

    @_('WHILE expression block')     # noqa
    def statement(self, parsed):
        return While(self.create_location(parsed.index, len(parsed.WHILE)),
                     parsed.expression, parsed.block)

    @_(       # noqa
        'FOR oneline_statement ";" expression ";" oneline_statement block')
    def statement(self, parsed):
        return For(self.create_location(parsed.index, len(parsed.FOR)),
                   parsed.oneline_statement0, parsed.expression,
                   parsed.oneline_statement1, parsed.block)

    @_('IF expression block elif_parts else_part')  # noqa
    def statement(self, parsed):
        return If(self.create_location(parsed.index, len(parsed.IF)),
                  [(parsed.expression, parsed.block)] + parsed.elif_parts,
                  parsed.else_part)

    @_('elif_parts elif_part')
    def elif_parts(self, parsed):
        return parsed.elif_parts + [parsed.elif_part]

    @_('')      # noqa
    def elif_parts(self, parsed):
        return []

    @_('ELIF expression block')
    def elif_part(self, parsed):
        return (parsed.expression, parsed.block)

    @_('ELSE block')
    def else_part(self, parsed):
        return parsed.block

    @_('')      # noqa
    def else_part(self, parsed):
        return []

    # function definitions
    # ~~~~~~~~~~~~~~~~~~~~

    @_('type ID')
    def arg_spec(self, parsed):
        return (parsed.type, parsed.ID,
                self.create_location(parsed.index, len(parsed.ID)))

    @_('')
    def arg_spec_list(self, parsed):
        return []

    @_('nonempty_arg_spec_list')      # noqa
    def arg_spec_list(self, parsed):
        return parsed.nonempty_arg_spec_list

    @_('nonempty_arg_spec_list "," arg_spec')
    def nonempty_arg_spec_list(self, parsed):
        return parsed.nonempty_arg_spec_list + [parsed.arg_spec]

    @_('arg_spec')      # noqa
    def nonempty_arg_spec_list(self, parsed):
        return [parsed.arg_spec]

    @_('FUNC ID "(" arg_spec_list ")" ARROW return_type block')      # noqa
    @_('FUNC ID create_generic "(" arg_spec_list ")" ARROW return_type block')
    def statement(self, parsed):
        generics = getattr(parsed, 'create_generic', None)
        if generics is not None:
            _duplicate_check(generics, "generic type")
        _duplicate_check(((arg[1], arg[2]) for arg in parsed.arg_spec_list),
                         "argument")

        return FuncDefinition(
            self.create_location(parsed.index, len(parsed.FUNC)), parsed.ID,
            generics, parsed.arg_spec_list, parsed.return_type, parsed.block)

    @_('VOID')
    def return_type(self, parsed):
        return None

    @_('type')      # noqa
    def return_type(self, parsed):
        return parsed.type

    @_('INDENT statements DEDENT')
    def block(self, parsed):
        return parsed.statements

    # one-line statements
    # ~~~~~~~~~~~~~~~~~~~

    @_('LET ID "=" expression')
    def oneline_statement(self, parsed):
        end = (parsed.expression.location.offset +
               parsed.expression.location.length)
        return Let(self.create_location(parsed.index, end - parsed.index),
                   parsed.ID, parsed.expression)

    @_('YIELD expression')      # noqa
    def oneline_statement(self, parsed):
        return Yield(self.create_location(parsed.index, len(parsed.YIELD)),
                     parsed.expression)

    @_('RETURN expression')      # noqa
    def oneline_statement(self, parsed):
        return Return(self.create_location(parsed.index, len(parsed.RETURN)),
                      parsed.expression)

    @_('RETURN')      # noqa
    def oneline_statement(self, parsed):
        return Return(self.create_location(parsed.index, len(parsed.RETURN)),
                      None)

    @_('VOID')      # noqa
    def oneline_statement(self, parsed):
        return VoidStatement(
            self.create_location(parsed.index, len(parsed.VOID)))

    @_('expression')      # noqa
    def oneline_statement(self, parsed):
        return parsed.expression

    @_('ID "=" expression')      # noqa
    def oneline_statement(self, parsed):
        target_location = self.create_location(parsed.index, len(parsed.ID))
        return SetVar(target_location + parsed.expression.location,
                      parsed.ID, parsed.expression)

    # expressions and operators
    # ~~~~~~~~~~~~~~~~~~~~~~~~~

    @_('simple_expression')
    def expression(self, parsed):
        return parsed.simple_expression

    @_expression_class(BinaryOperator)      # noqa
    @_('expression "+" expression',
       'expression "-" expression',
       'expression "*" expression',
       'expression EQ expression',
       'expression NE expression')
    def expression(self, parsed):
        lhs = parsed.expression0
        rhs = parsed.expression1
        return BinaryOperator(lhs.location + rhs.location, parsed[1], lhs, rhs)

    @_expression_class(PrefixOperator)      # noqa
    @_('"-" expression')
    def expression(self, parsed):
        op_location = self.create_location(parsed.index, len('-'))
        return PrefixOperator(
            op_location + parsed.expression.location, '-', parsed.expression)
        raise RuntimeError

    @_expression_class(FuncCall)      # noqa
    @_('expression "`" expression "`" expression')
    def expression(self, parsed):
        lhs = parsed.expression0
        function = parsed.expression1
        rhs = parsed.expression2
        return FuncCall(lhs.location + rhs.location, function, [lhs, rhs])

    # simple expressions
    # ~~~~~~~~~~~~~~~~~~

    @_expression_class(GetAttr)
    @_expression_class(FuncCall)
    @_('simple_expression trailer')
    def simple_expression(self, parsed):
        kind, value, location = parsed.trailer
        if kind == 'attribute':
            return GetAttr(location, parsed.simple_expression, value)
        if kind == 'call':
            return FuncCall(location, parsed.simple_expression, value)
        raise NotImplementedError(kind)     # pragma: no cover

    @_('simple_expression_no_trailers')      # noqa
    def simple_expression(self, parsed):
        return parsed.simple_expression_no_trailers

    @_('STRING')
    def simple_expression_no_trailers(self, parsed):
        location = common.Location(
            self.filename, parsed.index, len(parsed.STRING))
        return self.handle_string_literal(
            parsed.STRING, location)

    @_expression_class(Integer)      # noqa
    @_('INTEGER')
    def simple_expression_no_trailers(self, parsed):
        return Integer(self.create_location(parsed.index, len(parsed.INTEGER)),
                       int(parsed.INTEGER))

    @_expression_class(GetVar)      # noqa
    @_('ID')
    def simple_expression_no_trailers(self, parsed):
        return GetVar(self.create_location(parsed.index, len(parsed.ID)),
                      parsed.ID)

    @_expression_class(FromGeneric)      # noqa
    @_('ID from_generic')
    def simple_expression_no_trailers(self, parsed):
        types, end_location = parsed.from_generic
        return FromGeneric(
            self.create_location(parsed.index, end_location - parsed.index),
            parsed.ID, types)

    # expression trailers
    # ~~~~~~~~~~~~~~~~~~~

    @_('"(" expression ")"')      # noqa
    def simple_expression_no_trailers(self, parsed):
        return parsed.expression

    @_('"." ID')
    def trailer(self, parsed):
        dot_location = self.create_location(parsed.index, len(parsed[0]))
        return ('attribute', parsed.ID, dot_location)

    @_('"(" expression_list ")"')      # noqa
    def trailer(self, parsed):
        start_index = parsed.index
        end_index = self.last_token_offset() + len(')')
        location = self.create_location(start_index, end_index - start_index)
        return ('call', parsed.expression_list, location)

    @_('')
    def expression_list(self, parsed):
        return []

    @_('nonempty_expression_list')      # noqa
    def expression_list(self, parsed):
        return parsed.nonempty_expression_list

    @_('nonempty_expression_list "," expression')
    def nonempty_expression_list(self, parsed):
        return parsed.nonempty_expression_list + [parsed.expression]

    @_('expression')      # noqa
    def nonempty_expression_list(self, parsed):
        return [parsed.expression]

    # generics
    # ~~~~~~~~

    @_('"[" type_list "]"')
    def from_generic(self, parsed):
        end_of_close_bracket_offset = self.last_token_offset() + len(']')
        return (parsed.type_list, end_of_close_bracket_offset)

    @_('type_list "," type')
    def type_list(self, parsed):
        return parsed.type_list + [parsed.type]

    @_('type')      # noqa
    def type_list(self, parsed):
        return [parsed.type]

    @_('"[" generic_name_list "]"')
    def create_generic(self, parsed):
        return parsed.generic_name_list

    @_('generic_name_list "," generic_name')
    def generic_name_list(self, parsed):
        return parsed.generic_name_list + [parsed.generic_name]

    @_('generic_name')      # noqa
    def generic_name_list(self, parsed):
        return [parsed.generic_name]

    @_('ID')
    def generic_name(self, parsed):
        return (parsed.ID, self.create_location(parsed.index, len(parsed.ID)))


def parse(filename, code):
    return AsdaParser(filename).parse(tokenizer.tokenize(filename, code))


if __name__ == '__main__':
    print(parse('', '-x*y'))
