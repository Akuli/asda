"""
Code like this

    if x:
        print(a)
    else:
        print(b)
    print("hello")

produces a decision tree like this:

               ...

                |
                V
        ,---is x true?--.
        |yes          no|
        |               |
        V               V
    call print      call print
    with a as       with a as
     the only        the only
     argument        argument
        |               |
        '-------.-------'
                |
           create a new
            ObjectId()
           that refers
          to the string
             "Hello"
                |
                V
            call print

Above a and b are ObjectIds coming from variables, but not all ObjectIds have
a variable. The decision tree is optimized and then later turned into
operations on a stack of objects.
"""

import collections
import functools
import io
import itertools
import random
import pathlib
import subprocess
import tempfile
import typing

import attr

from asdac import utils
from asdac.common import Location
from asdac.objects import Function, Variable, VariableKind


@attr.s(auto_attribs=True, eq=False, order=False, frozen=True, repr=False)
class ObjectId:
    variable: typing.Optional[Variable] = None

    def __repr__(self) -> str:
        # is short, but is good
        result = _objectid_debug_counter(self)
        if self.variable is not None:
            result += ' ' + self.variable.name
        return f'<{result}>'


@functools.lru_cache(maxsize=None)
def _objectid_debug_counter(
        id: ObjectId, *,
        counter: typing.Iterator[int] = itertools.count(1)) -> str:
    return str(next(counter))


class Node:

    def __init__(self, location: typing.Optional[Location]):
        # number of elements has nothing to do with the type of the node
        # more than 1 means e.g. beginning of loop, 0 means unreachable code
        self.jumped_from: typing.Set[
            utils.AttributeReference[typing.Optional[Node]]] = set()

        # should be None for nodes created by the compiler
        self.location = location

    def ids_read(self) -> typing.Set[ObjectId]:
        """Which objects must already exist when this node runs?"""
        return set()

    def ids_written(self) -> typing.Set[ObjectId]:
        """Which object IDs does this node change when it runs?"""
        return set()

    def get_jumps_to_including_nones(
            self) -> typing.Iterable[typing.Optional['Node']]:
        """Return iterable of nodes that may be ran after running this node.

        If execution (of the function or file) may end at this node, the
        resulting iterable contains one or more Nones.
        """
        raise NotImplementedError

    def get_jumps_to(self) -> typing.Iterable['Node']:
        """Return iterable of nodes that may be ran after running this node."""
        return (node for node in self.get_jumps_to_including_nones()
                if node is not None)

    def change_jump_to(
            self,
            ref: utils.AttributeReference[typing.Optional['Node']],
            new: typing.Optional['Node']) -> None:
        old = ref.get()
        if old is not None:
            old.jumped_from.remove(ref)

        ref.set(new)
        assert ref.get() is new

        if new is not None:
            # can't jump to Start, avoids special cases
            # but you can jump to the node after the Start node
            assert not isinstance(new, Start)

            assert ref not in new.jumped_from
            new.jumped_from.add(ref)

    def __repr__(self) -> str:
        debug_string = _get_debug_string(self)
        if debug_string is None:
            return super().__repr__()
        return '<dtree.%s: %s, at %#x>' % (type(self).__name__, debug_string,
                                           id(self))


# a node that can be used like:
#    something --> this node --> something
class PassThroughNode(Node):

    def __init__(
            self, location: typing.Optional[Location],
            *args: typing.Any, **kwargs: typing.Any):
        super().__init__(location, *args, **kwargs)     # type: ignore
        self.next_node: typing.Optional[Node] = None

    def get_jumps_to_including_nones(
            self) -> typing.List[typing.Optional[Node]]:
        return [self.next_node]

    def set_next_node(self, next_node: Node) -> None:
        self.change_jump_to(
            utils.AttributeReference(self, 'next_node'), next_node)


class _LhsRhs(Node):

    def __init__(
            self,
            location: typing.Optional[Location],
            lhs_id: ObjectId,
            rhs_id: ObjectId,
            *args: typing.Any, **kwargs: typing.Any):
        super().__init__(location, *args, **kwargs)     # type: ignore
        self.lhs_id = lhs_id
        self.rhs_id = rhs_id

    def ids_read(self) -> typing.Set[ObjectId]:
        return {self.lhs_id, self.rhs_id}


class _OneResult(Node):

    def __init__(
            self,
            location: typing.Optional[Location],
            result_id: ObjectId,
            *args: typing.Any, **kwargs: typing.Any):
        super().__init__(location, *args, **kwargs)     # type: ignore
        self.result_id = result_id

    def ids_written(self) -> typing.Set[ObjectId]:
        return {self.result_id}


class _OneInputId(Node):

    def __init__(
            self,
            location: typing.Optional[Location],
            input_id: ObjectId,
            *args: typing.Any, **kwargs: typing.Any):
        super().__init__(location, *args, **kwargs)     # type: ignore
        self.input_id = input_id

    def ids_read(self) -> typing.Set[ObjectId]:
        return {self.input_id}


# execution begins here, having this avoids weird special cases
class Start(PassThroughNode):

    def __init__(
            self,
            location: typing.Optional[Location],
            arg_ids: typing.List[ObjectId]):
        self.arg_ids = arg_ids
        super().__init__(location)

    def ids_written(self) -> typing.Set[ObjectId]:
        return set(self.arg_ids)


class Throw(Node):

    # i hate pep8 line length but i stick with it anyway because pep8 is law
    def get_jumps_to_including_nones(
            self) -> typing.List[typing.Optional[Node]]:
        return []


class Return(Node):

    def __init__(
            self,
            location: typing.Optional[Location],
            value_id: typing.Optional[ObjectId]):
        super().__init__(location)
        self.value_id = value_id

    def ids_read(self) -> typing.Set[ObjectId]:
        if self.value_id is None:
            return set()
        return {self.value_id}

    def get_jumps_to_including_nones(
            self) -> typing.List[typing.Optional[Node]]:
        return []


class Assign(PassThroughNode, _OneInputId, _OneResult):
    pass


class GetBuiltinVar(PassThroughNode, _OneResult):

    def __init__(
            self,
            location: typing.Optional[Location],
            var: Variable,
            result_id: ObjectId):
        super().__init__(location, result_id)
        assert var.kind == VariableKind.BUILTIN
        self.var = var


class StrConstant(PassThroughNode, _OneResult):

    def __init__(
            self,
            location: typing.Optional[Location],
            python_string: str,
            result_id: ObjectId):
        super().__init__(location, result_id)
        self.python_string = python_string


class IntConstant(PassThroughNode, _OneResult):

    def __init__(
            self,
            location: typing.Optional[Location],
            python_int: int,
            result_id: ObjectId):
        super().__init__(location, result_id)
        self.python_int = python_int


# can't use _OneResult because result_id is Optional
class CallFunction(PassThroughNode):

    def __init__(
            self,
            location: typing.Optional[Location],
            function: Function,
            arg_ids: typing.List[ObjectId],
            result_id: typing.Optional[ObjectId] = None):

        if result_id is None:
            assert function.returntype is None
        else:
            assert function.returntype is not None

        self.function = function
        self.arg_ids = arg_ids
        self.result_id = result_id
        super().__init__(location)

    def ids_read(self) -> typing.Set[ObjectId]:
        return set(self.arg_ids)

    def ids_written(self) -> typing.Set[ObjectId]:
        if self.result_id is None:
            return set()
        return {self.result_id}


# TODO: read my wall of text, does it still apply?
#
# you might be thinking of implementing 'return blah' so that it leaves 'blah'
# on the stack and exits the function, but I thought about that for about 30
# minutes straight and it turned out to be surprisingly complicated
#
# there may be local variables (including the function's arguments) in the
# bottom of the stack, and they are cleared with nodes like
# PopOne(is_popping_a_dummy=True) when the function exits
#
# the return value must go before the local variables in the stack, because
# otherwise every PopOne(is_popping_a_dummy=True) has to move the return value
# object in the stack by one, which feels dumb (but maybe not too inefficient):
#
#   [var1, var2, var3, result]      # Function is running 'return result'
#   [var1, var2, result]            # PopOne(is_popping_a_dummy=True) ran
#
# i.e. PopOne, which used to be just decrementing stack top pointer (and
# possibly a decref), is now a more complicated thing that can in some cases
# delete stuff BEFORE the stack top? wtf. i don't like this
#
# I also thought about creating a special variable that would always go first
# in the stack and would hold the return value, but function arguments go first
# in the stack, so this would conflict with the first argument of the function.
# Unless I make the function arguments start at index 1 for value-returning
# functions and at index 0 for other functions. Would be a messy piece of shit.
#
# The solution is to store the return value into a special place outside the
# stack before local variables are popped off.


class StrJoin(PassThroughNode, _OneResult):

    def __init__(
            self,
            location: typing.Optional[Location],
            string_ids: typing.List[ObjectId],
            result_id: ObjectId):
        super().__init__(location, result_id)
        self.string_ids = string_ids

    def ids_read(self) -> typing.Set[ObjectId]:
        return set(self.string_ids)


class TwoWayDecision(Node):

    def __init__(
            self,
            location: typing.Optional[Location],
            *args: typing.Any, **kwargs: typing.Any):
        super().__init__(location, *args, **kwargs)     # type: ignore
        self.then: typing.Optional[Node] = None
        self.otherwise: typing.Optional[Node] = None

    def get_jumps_to_including_nones(
            self) -> typing.List[typing.Optional[Node]]:
        return [self.then, self.otherwise]

    def set_then(self, value: typing.Optional[Node]) -> None:
        self.change_jump_to(
            utils.AttributeReference(self, 'then'), value)

    def set_otherwise(self, value: typing.Optional[Node]) -> None:
        self.change_jump_to(
            utils.AttributeReference(self, 'otherwise'), value)


class BoolDecision(TwoWayDecision, _OneInputId):
    pass


def _get_debug_string(node: Node) -> typing.Optional[str]:
    if isinstance(node, GetBuiltinVar):
        return node.var.name
    if isinstance(node, IntConstant):
        return str(node.python_int)
    if isinstance(node, StrConstant):
        return repr(node.python_string)
    if isinstance(node, CallFunction):
        return f'{node.function.get_string()}'
    return None


T = typing.TypeVar('T')


def _items_in_all_sets(sets: typing.Iterable[typing.Set[T]]) -> typing.Set[T]:
    return functools.reduce(set.intersection, sets)


# if we have (in graphviz syntax) a->c->d->f->g, b->e->f->g
# then find_merge(a, b) returns f, because that's first node where they merge
# may return None, if paths never merge together
# see tests for corner cases
#
# callback(node) should return an iterable of nodes after "node->", e.g. in
# above example, callback(a) could return [c]
#
# TODO: better algorithm? i found this
# https://www.hackerrank.com/topics/lowest-common-ancestor
# but doesn't seem to handle cyclic graphs?
def find_merge(
    nodes: typing.Iterable[Node],
    *,
    callback: typing.Callable[
        [Node], typing.Iterable[Node]] = lambda n: n.get_jumps_to(),
) -> typing.Optional[Node]:
    # {node: set of other nodes reachable from the node}
    reachable_dict = {node: {node} for node in nodes}

    # finding merge of empty iterable of nodes doesn't make sense
    assert reachable_dict

    while True:
        reachable_from_all_nodes = _items_in_all_sets(reachable_dict.values())
        try:
            return reachable_from_all_nodes.pop()
        except KeyError:
            pass

        did_something = False
        for reaching_set in reachable_dict.values():
            # TODO: this goes through the same nodes over and over again
            #       could be optimized
            for node in reaching_set.copy():
                for newly_reachable in callback(node):
                    if newly_reachable not in reaching_set:
                        reaching_set.add(newly_reachable)
                        did_something = True

        if not did_something:
            return None


# TODO: cache result somewhere, but careful with invalidation?
def get_all_nodes(
        root_node: Node, include_root: bool = True) -> typing.Set[Node]:
    result = set()

    # to_visit set should be faster than recursion
    if include_root:
        to_visit = {root_node}
    else:
        to_visit = set(root_node.get_jumps_to())

    while to_visit:
        node = to_visit.pop()
        if node not in result:
            result.add(node)
            to_visit.update(node.get_jumps_to())

    return result


# this may be slow
def clean_all_unreachable_nodes(start_node: Start) -> None:
    reachable_nodes = get_all_nodes(start_node)
    for node in reachable_nodes:
        for ref in node.jumped_from.copy():
            if ref.objekt not in reachable_nodes:
                ref.set(None)
                node.jumped_from.remove(ref)


def clean_unreachable_nodes_given_one_of_them(unreachable_head: Node) -> None:
    unreachable = set()
    to_visit = collections.deque([unreachable_head])
    did_nothing_count = 0

    # TODO: does this loop terminate if there is a cycle of unreachable nodes?
    while did_nothing_count < len(to_visit):
        assert to_visit
        node = to_visit.popleft()

        if all(ref.objekt in unreachable for ref in node.jumped_from):
            unreachable.add(node)
            to_visit.extend(node.get_jumps_to())
            did_nothing_count = 0
        else:
            to_visit.append(node)
            did_nothing_count += 1

    assert unreachable_head in unreachable

    # now to_visit contains reachable nodes that the unreachable nodes jump to
    for reachable_node in to_visit:
        for ref in reachable_node.jumped_from.copy():
            if ref.objekt in unreachable:
                reachable_node.jumped_from.remove(ref)


# to use this, create the new node and set its .next_node or similar
# then call this function
def replace_node(old: Node, new: typing.Optional[Node]) -> None:
    if new is not None:
        new.jumped_from.update(old.jumped_from)

    for ref in old.jumped_from:
        ref.set(new)

    old.jumped_from.clear()
    clean_unreachable_nodes_given_one_of_them(old)


# could be optimized more, but not a problem because this is used only for
# graphviz stuff
def _get_unreachable_nodes(
        reachable_nodes: typing.Set[Node]) -> typing.Set[Node]:
    to_visit = reachable_nodes.copy()
    reachable_and_unreachable = set()

    while to_visit:
        node = to_visit.pop()
        if node in reachable_and_unreachable:
            continue

        reachable_and_unreachable.add(node)
        to_visit.update(
            typing.cast(Node, ref.objekt) for ref in node.jumped_from)

    return reachable_and_unreachable - reachable_nodes


def _random_color() -> str:
    rgb = (0, 0, 0)
    while sum(rgb)/len(rgb) < 0x80:   # too dark, create new color
        rgb = (random.randint(0x00, 0xff),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff))
    return '#%02x%02x%02x' % rgb


def _graphviz_node_id(node: Node) -> str:
    return 'node' + str(id(node))


def _graphviz_code(
        root_node: Node,
        label_extra: str = '') -> typing.Iterator[str]:
    reachable = get_all_nodes(root_node)
    unreachable = _get_unreachable_nodes(reachable)
    assert not (reachable & unreachable)

    for node in (reachable | unreachable):
        parts = [type(node).__name__]
        # TODO: display location?

        debug_string = _get_debug_string(node)
        if debug_string is not None:
            parts.append(debug_string)

        if node in unreachable:
            parts.append('UNREACHABLE')

        if isinstance(node, _OneInputId):
            parts.append(f'input={node.input_id}')
        elif isinstance(node, _LhsRhs):
            parts.append(f'lhs={node.lhs_id} rhs={node.rhs_id}')
        elif isinstance(node, CallFunction):
            parts.append(f'args={node.arg_ids}')
            parts.append(f'result_id={node.result_id}')
        elif isinstance(node, Start):
            parts.append(f'arg_ids={node.arg_ids}')

        if isinstance(node, _OneResult):
            parts.append(f'result_id={node.result_id}')

        for to in node.get_jumps_to():
            if node not in (ref.objekt for ref in to.jumped_from):
                parts.append('HAS PROBLEMS with jumped_from stuff')

        yield '%s [label="%s"];\n' % (
            _graphviz_node_id(node), '\n'.join(parts).replace('"', r'\"'))

#        if isinstance(node, CreateFunction):
#            color = _random_color()
#            yield 'subgraph cluster%s {\n' % _graphviz_node_id(node)
#            yield 'style=filled;\n'
#            yield 'color="%s";\n' % color
#            yield from _graphviz_code(node.body_root_node, "FUNCTION BODY")
#            yield '}\n'
#            yield '%s [style=filled, fillcolor="%s"];' % (
#                _graphviz_node_id(node), color)

        if isinstance(node, TwoWayDecision):
            # color 'then' with green, 'otherwise' with red
            if node.then is not None:
                yield '%s -> %s [color=green]\n' % (
                    _graphviz_node_id(node), _graphviz_node_id(node.then))
            if node.otherwise is not None:
                yield '%s -> %s [color=red]\n' % (
                    _graphviz_node_id(node), _graphviz_node_id(node.otherwise))
        else:
            for to in node.get_jumps_to():
                yield '%s -> %s\n' % (
                    _graphviz_node_id(node), _graphviz_node_id(to))


# for debugging, displays a visual representation of the tree
def graphviz(root_node: Node, filename_without_ext: str) -> None:
    path = pathlib.Path(tempfile.gettempdir()) / 'asdac'
    path.mkdir(parents=True, exist_ok=True)
    png = path / (filename_without_ext + '.png')

    # overwrites the png file if it exists
    dot = subprocess.Popen(['dot', '-o', str(png), '-T', 'png'],
                           stdin=subprocess.PIPE)
    raw_stdin = dot.stdin
    assert raw_stdin is not None
    dot_stdin = io.TextIOWrapper(raw_stdin)
    dot_stdin.write('digraph {\n')
    dot_stdin.writelines(_graphviz_code(root_node))
    dot_stdin.write('}\n')
    dot_stdin.flush()
    dot_stdin.close()

    status = dot.wait()
    assert status == 0

    print("decision_tree.graphviz(): see", str(png))
