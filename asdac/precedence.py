import enum
import typing

import attr

from asdac.ast import Expression
from asdac.common import CompileError, Location
from asdac.tokenizer import Token


@attr.s(auto_attribs=True, cmp=False, frozen=True)
class Operation:
    location: Location
    operator: str

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class PrefixOperation(Operation):
    expression: Expression

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class BinaryOperation(Operation):
    lhs: Expression
    rhs: Expression

@attr.s(auto_attribs=True, cmp=False, frozen=True)
class TernaryOperation(Operation):
    lhs: Expression
    mid: Expression
    rhs: Expression


class Flags(enum.IntFlag):
    PREFIX = 1 << 0             # -x
    BINARY = 1 << 1             # x + y
    TERNARY = 1 << 2            # x `y` z
    BINARY_CHAINING = 1 << 3    # allow writing e.g. x + y + z


PRECEDENCE_LIST = [
    [('*', Flags.BINARY | Flags.BINARY_CHAINING)],
    [('+', Flags.BINARY | Flags.BINARY_CHAINING),
     ('-', Flags.BINARY | Flags.BINARY_CHAINING | Flags.PREFIX)],
    [('==', Flags.BINARY),
     ('!=', Flags.BINARY)],
    [('.', Flags.BINARY | Flags.BINARY_CHAINING)],  # TODO: move higher in list
    [('`', Flags.TERNARY)],
]


T = typing.TypeVar('T')


def _find_adjacent_items(
    the_list: typing.List[T],
    key: typing.Callable[[T, T], bool],
) -> typing.Optional[typing.Tuple[T, T]]:
    for item1, item2 in zip(the_list, the_list[1:]):
        if key(item1, item2):
            return (item1, item2)
    return None


# The idea:
#
#       x * y + a * b
#   --> [x, '*', y, '+', a, '*', b]
#   --> [(x, '*', y), '+', ('a', '*', 'b')]
#   --> [((x, '*', y), '+', ('a', '*', 'b'))]
#   --> ((x, '*', y), '+', ('a', '*', 'b'))
#
# then recurse through that like any other ast, and we have operator precedence
class _PrecedenceHandler:

    def __init__(
        self,
        parts: typing.List[typing.Union[Expression, Token]],
        operation_to_expression: typing.Callable[[Operation], Expression],
    ):
        # this is the list that eventually contains only 1 expression
        self.parts = parts.copy()
        assert self.parts

        self.operation_to_expression = operation_to_expression

    # there must not be two expressions next to each other without an
    # operator between
    def _check_no_adjacent_expressions(self) -> None:
        adjacent_expression_parts = _find_adjacent_items(self.parts, (
          lambda part1, part2: (
            isinstance(part1, Expression) and isinstance(part2, Expression))))

        if adjacent_expression_parts is not None:
            part1, part2 = adjacent_expression_parts
            # if you have an idea for a better error message, add that here
            raise CompileError(
                "invalid syntax", part1.location + part2.location)

    def _find_op(
        self,
        op_flags_pairs: typing.List[typing.Tuple[str, Flags]],
    ) -> typing.Optional[typing.Tuple[int, Flags, Token]]:
        ops = [op for op, flags in op_flags_pairs]

        for parts_index, part in enumerate(self.parts):
            if isinstance(part, Expression):
                continue
            token = typing.cast(Token, part.value)

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

    def _handle_ternary(
        self,
        before: typing.Optional[Expression],
        this_token: Token,
        after: typing.Optional[Expression],
        that_token: typing.Optional[Token],
        more_after: typing.Optional[Expression],
    ) -> typing.Tuple[int, int, TernaryOperation]:
        if (
          before is None or
          after is None or
          that_token is None or
          this_token.value != that_token.value or
          more_after is None):
            assert this_token is not None
            raise CompileError(
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

        result = TernaryOperation(location, this_token.value, before, after,
                                 more_after)
        return (1, 3, result)

    def _binary_is_chained_but_shouldnt_be(
        self,
        that_token: Token,
        other_op: str,
        other_flags: Flags,
    ) -> bool:
        return bool(other_op == that_token.value and
                    (other_flags & Flags.BINARY) and
                    not (other_flags & Flags.BINARY_CHAINING))

    def _handle_binary_or_prefix(
        self,
        before: typing.Optional[Expression],
        this_token: Token,
        after: typing.Optional[Expression],
        that_token: typing.Optional[Token],
        op_flags_pairs: typing.List[typing.Tuple[str, Flags]],
        flags: Flags,
    ) -> typing.Tuple[int, int, Operation]:

        result: Operation

        if before is None and after is not None and (flags & Flags.PREFIX):
            result = PrefixOperation(
                this_token.location, this_token.value, after)
            return (0, 1, result)

        if before is not None and after is not None and (flags & Flags.BINARY):
            if (
              that_token is not None and
              not (flags & Flags.BINARY_CHAINING) and
              any(self._binary_is_chained_but_shouldnt_be(that_token, *pair)
                  for pair in op_flags_pairs)):
                raise CompileError(
                    "'a {0} b {1} c' is not valid syntax"
                    .format(this_token.value, that_token.value),
                    that_token.location)

            result = BinaryOperation(
                this_token.location, this_token.value, before, after)
            return (1, 1, result)

        raise CompileError(
            "'%s' cannot be used like this" % this_token.value,
            this_token.location)

    def _get_expression(self, index: int) -> typing.Optional[Expression]:
        if 0 <= index < len(self.parts):
            value = self.parts[index]
            if isinstance(value, Expression):
                return value
        return None

    def _get_token(self, index: int) -> typing.Optional[Token]:
        if 0 <= index < len(self.parts):
            value = self.parts[index]
            if isinstance(value, Token):
                return value
        return None

    def run(self) -> Expression:
        self._check_no_adjacent_expressions()

        for op_flags_pairs in PRECEDENCE_LIST:
            while True:
                find_result = self._find_op(op_flags_pairs)
                if find_result is None:
                    break
                index, flags, this_token = find_result

                before = self._get_expression(index-1)
                after = self._get_expression(index+1)
                that_token = self._get_token(index+2)
                more_after = self._get_expression(index+3)

                oper: Operation
                if flags & Flags.TERNARY:
                    assert flags == Flags.TERNARY     # no other flags
                    before_count, after_count, oper = self._handle_ternary(
                        before, this_token, after, that_token, more_after)
                else:
                    before_count, after_count, oper = (
                        self._handle_binary_or_prefix(
                            before, this_token, after, that_token,
                            op_flags_pairs, flags))

                result = self.operation_to_expression(oper)

                start_index = index - before_count
                end_index = index + 1 + after_count
                assert start_index >= 0
                assert end_index <= len(self.parts)
                self.parts[start_index:end_index] = [result]

        [the_result] = self.parts
        assert isinstance(the_result, Expression)
        return the_result


def handle_precedence(
    parts: typing.List[typing.Union[Expression, Token]],
    operation_to_expression: typing.Callable[[Operation], Expression],
) -> Expression:
    return _PrecedenceHandler(parts, operation_to_expression).run()
