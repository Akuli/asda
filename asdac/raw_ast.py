import collections
import functools
import itertools

from asdac import common, string_parser, tokenizer


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


class _TokenIterator:

    def __init__(self, token_iterable):
        self._iterator = iter(token_iterable)
        self.index = 0

    def copy(self):
        self._iterator, copied = itertools.tee(self._iterator)
        result = _TokenIterator(copied)
        result.index = self.index
        return result

    def become_like(self, copy):
        """Calls next_token() repeatedly so that self is at same state as copy.

        This is useful when copy has been used for doing something, but that's
        an implementation detail, and you want to instead make everything look
        like self had been used instead.
        """
        while self.index < copy.index:
            self.next_token()
        assert self.index == copy.index

    def next_token(self, required_kind=None, required_value=None):
        try:
            token = next(self._iterator)
        except StopIteration as e:
            # FIXME: this needs location
            raise common.CompileError("unexpected end of file", None)

        self.index += 1

        error = functools.partial(common.CompileError, location=token.location)
        if required_value is not None and token.value != required_value:
            raise error("expected %r, got %r" % (required_value, token.value))
        if required_kind is not None and token.kind != required_kind:
            raise error("expected %s, got %r" % (required_kind, token.value))

        return token

    def eof(self):
        try:
            next(self.copy()._iterator)
            return False
        except StopIteration:
            return True


# have fun figuring this out
def _grammar_func(func):
    return lambda *args, **kwargs: lambda tokens: func(tokens, *args, **kwargs)


# the parser works by trying to parse all kinds of things until one of the
# things parses successfully, but if this is raised, it stops trying and lets
# this "bubble up"
class _CompileErrorToNotBeCatched(Exception):

    # Exception.__init__ stores all non-keyword arguments to .args attribute
    # which is handy for this

    def as_real_compile_error(self):
        return common.CompileError(*self.args)

    @classmethod
    def from_real_compile_error(cls, error):
        return cls(error.message, error.location)


# if multiple choices are given, parses exactly one of them
#
# unlike most other grammar funcs, this takes _grammar keys as arguments, and
# this is actually the only way to use other parts of the _grammar
@_grammar_func
def _one_of(tokens, *grammar_keys):
    assert grammar_keys

    parsed = []     # contains (result, tokens_copy) pairs
    errors = []     # contains exception objects
    for key in grammar_keys:
        tokens_copy = tokens.copy()
        try:
            parsed.append((_grammar[key](tokens_copy), tokens_copy))
        except common.CompileError as e:
            errors.append(e)

    if not parsed:
        # nothing parsed successfully, but which error to report to user?

        # if everything is stuck at the first token, something is
        # wrong with it
        first = tokens.next_token()
        if all(err.location == first.location for err in errors):
            raise common.CompileError(
                "unexpected %s" % first.kind, first.location)

        print(errors)
        # if something parsed more and failed later, its error is likely
        # more helpful
        raise max(errors, key=(lambda err: err.location.start))

    assert len(parsed) == 1, parsed  # if this fails, the grammar is ambiguous
    result, tokens_copy = parsed[0]

    tokens.become_like(tokens_copy)
    return result


# can be called with 1 item only to make ast_creating_func get called
@_grammar_func
def _sequence(tokens, ast_creating_func, *item_grammar_funcs):
    assert item_grammar_funcs
    assert all(map(callable, item_grammar_funcs)), item_grammar_funcs
    copied_tokens = tokens.copy()
    parsed = [func(copied_tokens) for func in item_grammar_funcs]

    # something seemed to parse successfully, so there should be something
    assert not tokens.eof()

    first_token = tokens.next_token()
    last_token = first_token   # usually changed by while, but maybe not always
    while tokens.index < copied_tokens.index:
        last_token = tokens.next_token()
    assert tokens.index == copied_tokens.index

    location = first_token.location + last_token.location
    return ast_creating_func(location, *parsed)


@_grammar_func
def _token(tokens, kind=None, value=None):
    return tokens.next_token(kind, value)


_keyword = functools.partial(_token, 'keyword')
_op = functools.partial(_token, 'op')


# returns the value of the token, all other info is lost
@_grammar_func
def _optional(tokens, parse_func, nothing_value):
    # don't leave the tokens in partially used state
    tokens_copy = tokens.copy()

    try:
        result = parse_func(tokens_copy)
    except common.CompileError:
        return nothing_value

    tokens.become_like(tokens_copy)
    return result


@_grammar_func
def _repeat(tokens, parse_func, allow_nothing):
    result = []
    while True:
        # don't leave the tokens in partially used state on error
        tokens_copy = tokens.copy()

        try:
            result.append(parse_func(tokens_copy))
        except common.CompileError as e:
            if (not result) and (not allow_nothing):
                raise e
            break
        else:
            tokens.become_like(tokens_copy)

    return result


def _commasep_list(parse_item, allow_nothing):
    def main_ast_creator(location, expression, more_expressions):
        return [expression] + more_expressions

    def sub_ast_creator(location, comma, expression):
        return expression

    result = _sequence(
        main_ast_creator, parse_item,
        _repeat(_sequence(sub_ast_creator, _op(','), parse_item), True))
    if allow_nothing:
        result = _optional(result, [])
    return result


def _handle_trailers(junk_location, expression, trailers):
    for kind, trailer_location, info in trailers:
        location = expression.location + trailer_location
        if kind == 'call':
            assert isinstance(info, list)   # argument list
            expression = FuncCall(location, expression, info)
        elif kind == 'attribute':
            assert isinstance(info, str)    # attribute name
            expression = GetAttr(location, expression, info)
    return expression


def _duplicate_check(names_and_locations, what_are_they):
    seen = set()
    for name, location in names_and_locations:
        if name in seen:
            raise _CompileErrorToNotBeCatched(
                "repeated %s name: %s" % (what_are_they, name), location)
        seen.add(name)


def _to_string(parsed):
    location = parsed.location      # because pep8 line length
    return FuncCall(location, GetAttr(location, parsed, 'to_string'), [])


def _handle_string_literal(location, string):
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
            tokens = _TokenIterator(tokenizer.tokenize(
                part_location.filename, value,
                initial_lineno=part_location.startline,
                initial_column=part_location.startcolumn))

            # make sure that there are some tokens, otherwise a thing in
            # _TokenIterator fails
            #
            # the parse() function at end of this file does that too,
            # because it does nothing if there are no tokens
            if tokens.eof():
                raise common.CompileError(
                    "you must put some code between { and }",
                    part_location)

            parts.append(_to_string(_grammar['expression'](tokens)))
            tokens.next_token('newline')    # added by tokenizer
            assert tokens.eof()     # if fails, string isn't one-line

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


def _check_1line_statement(location, statement):
    if not isinstance(statement, (Let, FuncCall, VoidStatement, Return,
                                  Yield, SetVar)):
        raise _CompileErrorToNotBeCatched("not a statement", location)

    return statement


def _handle_expression_statement_or_assignment(location, lhs, rhs):
    if rhs is None:    # expression statement
        return lhs

    if not isinstance(lhs, GetVar):
        raise _CompileErrorToNotBeCatched(
            "this is not something that can be assigned to",
            lhs.location)
    return SetVar(location, lhs.varname, rhs)


def _handle_possible_generic_lookup(ast_class, location, id_, generic_types):
    if generic_types is None:
        return ast_class(location, id_.value)
    return FromGeneric(location, id_.value, generic_types)


def _handle_generic_name_trailer(location, bracket1, type_tokens, bracket2):
    _duplicate_check(((token.value, token.location) for token in type_tokens),
                     'generic type')
    return [(token.value, token.location) for token in type_tokens]


def _handle_function_definition(location, func_keyword, name, generics,
                                bracket1, args, bracket2, arrow, returntype,
                                body):
    _duplicate_check(((name, loc) for tybe, name, loc in args), 'argument')
    return FuncDefinition(
        location, name.value, generics, args, returntype, body)


_grammar = {
    # statements
    'statement': _one_of('one-line statement and a newline', 'if statement',
                         'while loop', 'for loop', 'function definition'),
    'one-line statement and a newline': _sequence(
        lambda loc, statement, newline: statement,
        _one_of('one-line statement'), _token('newline')),
    'one-line statement': _sequence(_check_1line_statement, _one_of(
        'expression statement or assignment', 'void statement',
        'let statement', 'return statement', 'yield statement')),

    # not all expressions are valid one-line statements, but that's handled
    # in _check_1line_statement() instead because that way is easier
    #
    # this is here because 'expr1 = expr2' could be also parsed as 'expr1', and
    # this avoids ambiguity
    'expression statement or assignment': _sequence(
        _handle_expression_statement_or_assignment,
        _one_of('expression'),
        _optional(_sequence(lambda location, eq, rhs: rhs,
                            _op('='), _one_of('expression')), None)),

    'void statement': _sequence(
        lambda loc, void: VoidStatement(loc),
        _keyword('void')),
    'let statement': _sequence(
        lambda loc, let, var, eq, value: Let(loc, var.value, value),
        _keyword('let'), _token('id'), _op('='), _one_of('expression')),
    'return statement': _sequence(
        lambda loc, return_, value: Return(loc, value),
        _keyword('return'), _optional(_one_of('expression'), None)),
    'yield statement': _sequence(
        lambda loc, yield_, value: Yield(loc, value),
        _keyword('yield'), _one_of('expression')),

    'while loop': _sequence(
        lambda loc, while_, cond, body: While(loc, cond, body),
        _keyword('while'), _one_of('expression'), _one_of('body')),

    'for loop': _sequence(
        lambda loc, for_, init, semi1, cond, semi2, incr, body: For(
            loc, init, cond, incr, body),
        _keyword('for'),
        _one_of('one-line statement'), _op(';'),
        _one_of('expression'), _op(';'),
        _one_of('one-line statement'),
        _one_of('body')),

    'if statement': _sequence(
        lambda loc, if_, elifs, elsebody: If(loc, [if_] + elifs, elsebody),
        _one_of('if statement if part'),
        _repeat(_one_of('if statement elif part'), True),
        _optional(_one_of('if statement else part'), [])),
    'if statement if part': _sequence(
        lambda loc, if_, cond, body: (cond, body),
        _keyword('if'), _one_of('expression'), _one_of('body')),
    'if statement elif part': _sequence(
        lambda loc, elif_, cond, body: (cond, body),
        _keyword('elif'), _one_of('expression'), _one_of('body')),
    'if statement else part': _sequence(
        lambda loc, else_keyword, body: body,
        _keyword('else'), _one_of('body')),

    'function definition': _sequence(
        _handle_function_definition,
        _keyword('func'), _token('id'),
        _optional(_one_of('generic name trailer'), None), _op('('),
        _commasep_list(_one_of('argument specification'), True), _op(')'),
        _op('->'), _one_of('return type specification'), _one_of('body')),
    'argument specification': _sequence(
        lambda loc, tybe, name: (tybe, name.value, name.location),
        _one_of('type'), _token('id')),
    'return type specification': _one_of('void return type', 'type'),
    'void return type': _sequence(
        lambda loc, void_token: None,
        _token('keyword', 'void')),

    # expressions
    'expression': _sequence(
        _handle_trailers, _one_of('expression without trailers'),
        _repeat(_one_of('expression trailer'), True)),
    'expression without trailers': _one_of(
        'variable or generic function lookup', 'string literal',
        'integer literal'),
    'variable or generic function lookup': _sequence(
        functools.partial(_handle_possible_generic_lookup, GetVar),
        _token('id'), _optional(_one_of('generic type trailer'), None)),
    'string literal': _sequence(
        lambda loc, token: _handle_string_literal(loc, token.value),
        _token('string')),
    'integer literal': _sequence(
        lambda loc, token: Integer(loc, int(token.value)),
        _token('integer')),

    'expression trailer': _one_of(
        'attribute lookup trailer', 'function call trailer'),
    'attribute lookup trailer': _sequence(
        lambda loc, dot, attrib: ('attribute', loc, attrib.value),
        _op('.'), _token('id')),
    'function call trailer': _sequence(
        lambda loc, paren1, args, paren2: ('call', loc, args),
        _op('('), _commasep_list(_one_of('expression'), True), _op(')')),

    # types
    # TODO: update this when not all type names are id tokens
    'type': _sequence(
        functools.partial(_handle_possible_generic_lookup, GetType),
        _token('id'), _optional(_one_of('generic type trailer'), None)),

    # misc
    'generic type trailer': _sequence(
        lambda location, bracket1, types, bracket2: types,
        _op('['), _commasep_list(_one_of('type'), False), _op(']')),
    'generic name trailer': _sequence(
        _handle_generic_name_trailer,
        _op('['), _commasep_list(_token('id'), False), _op(']')),
    'body': _sequence(
        lambda loc, indent, statements, dedent: statements,
        _token('indent'), _repeat(_one_of('statement'), False),
        _token('dedent')),
}


def parse(filename, code):
    try:
        tokens = _TokenIterator(tokenizer.tokenize(filename, code))
        while not tokens.eof():
            yield _grammar['statement'](tokens)
    except _CompileErrorToNotBeCatched as e:
        raise e.as_real_compile_error() from e
