"""
Code like this

    if x:
        print(a)
    else:
        print(b)
    print(c)

produces a decision tree like this:

               ...

                |
                V
        ,---is x true?--.
        |yes          no|
        |               |
        V               V
    push print      push print
     to stack        to stack
        |               |
        V               V
      push a          push b
     to stack        to stack
        |               |
        V               V
     function        function
       call            call
        |               |
        '-> push print <'
             to stack
                |
                V
             function
               call
                |
                V
               ...

this can be optimized to fit into smaller space because it's repetitive, which
is one reason for having a decision tree compile step
"""

import collections
import functools
import io
import random
import pathlib
import subprocess
import tempfile
import typing

from asdac import common, cooked_ast, utils


class Node:
    """
    size_delta tells how many objects this node pushes to the stack (positive)
    and pops from stack (negative). For example, if your node pops two
    objects, does something with them, and pushes the result to the stack, you
    should set size_delta to -2 + 1 = -1.

    use_count tells how many topmost objects of the stack this node uses. In
    the above example, it should be 2.
    """

    def __init__(
            self, *,
            use_count: int,
            size_delta: int,
            location: typing.Optional[common.Location] = None):
        self.use_count = use_count
        self.size_delta = size_delta

        assert use_count >= 0
        if size_delta < 0:
            assert use_count >= abs(size_delta)

        # contains AttributeReferences
        # number of elements has nothing to do with the type of the node
        # more than 1 means e.g. beginning of loop, 0 means unreachable code
        self.jumped_from: typing.Set[
            utils.AttributeReference[typing.Optional[Node]]] = set()

        # should be None for nodes created by the compiler
        self.location = location

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
            ref: utils.AttributeReference[typing.Optional[Node]],
            new: typing.Optional[Node]) -> None:
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
        return '<%s: %s, at %#x>' % (type(self).__name__, debug_string,
                                     id(self))


# a node that can be used like:
#    something --> this node --> something
class PassThroughNode(Node):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(**kwargs)
        self.next_node: typing.Optional[Node] = None

    def get_jumps_to_including_nones(
            self) -> typing.List[typing.Optional[Node]]:
        return [self.next_node]

    def set_next_node(self, next_node: Node) -> None:
        self.change_jump_to(
            utils.AttributeReference(self, 'next_node'), next_node)


# execution begins here, having this avoids weird special cases
class Start(PassThroughNode):

    def __init__(
            self, argvars: typing.List[cooked_ast.Variable],
            **kwargs: typing.Any):
        super().__init__(use_count=0, size_delta=len(argvars), **kwargs)
        self.argvars = argvars


class GetBuiltinVar(PassThroughNode):

    def __init__(self, varname: str, **kwargs: typing.Any):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.varname = varname


class ExportObject(PassThroughNode):

    def __init__(self, name: str, **kwargs: typing.Any):
        super().__init__(use_count=1, size_delta=-1, **kwargs)
        self.name = name


class PopOne(PassThroughNode):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=1, size_delta=-1, **kwargs)


class Plus(PassThroughNode):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=2, size_delta=-1, **kwargs)


class Times(PassThroughNode):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=2, size_delta=-1, **kwargs)


class Minus(PassThroughNode):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=2, size_delta=-1, **kwargs)


class PrefixMinus(PassThroughNode):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=1, size_delta=0, **kwargs)


# TODO: optimize dead code after Throw? maybe similarly to Return?
class Throw(PassThroughNode):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=1, size_delta=-1, **kwargs)


class StrConstant(PassThroughNode):

    def __init__(self, python_string: str, **kwargs: typing.Any):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.python_string = python_string


class IntConstant(PassThroughNode):

    def __init__(self, python_int: int, **kwargs: typing.Any):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.python_int = python_int


class CallFunction(PassThroughNode):

    def __init__(self, function: cooked_ast.Function,
                 how_many_args: int, is_returning: bool, **kwargs: typing.Any):
        self.function = function
        self.how_many_args = how_many_args
        self.is_returning = is_returning

        super().__init__(
            use_count=how_many_args,
            size_delta=(-how_many_args + int(bool(is_returning))),
            **kwargs)


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


class StrJoin(PassThroughNode):

    def __init__(self, how_many_strings: int, **kwargs: typing.Any):
        super().__init__(
            use_count=how_many_strings, size_delta=(-how_many_strings + 1),
            **kwargs)
        self.how_many_strings = how_many_strings


class TwoWayDecision(Node):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(**kwargs)
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


class BoolDecision(TwoWayDecision):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=1, size_delta=-1, **kwargs)


class IntEqualDecision(TwoWayDecision):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=2, size_delta=-2, **kwargs)


class StrEqualDecision(TwoWayDecision):

    def __init__(self, **kwargs: typing.Any):
        super().__init__(use_count=2, size_delta=-2, **kwargs)


def _get_debug_string(node: Node) -> typing.Optional[str]:
    if isinstance(node, GetBuiltinVar):
        return node.varname
    if isinstance(node, IntConstant):
        return str(node.python_int)
    if isinstance(node, StrConstant):
        return repr(node.python_string)
    if isinstance(node, CallFunction):
        return (
            node.function.get_string()
            + ', ' + ('%d args' % node.how_many_args))
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


# size_dict is like this {node: stack size BEFORE running the node}
def _get_stack_sizes_to_dict(
        node: Node,
        size: int,
        size_dict: typing.Dict[Node, int]) -> None:
    assert node is not None

    while True:
        if node in size_dict:
            assert size == size_dict[node]
            return

        size_dict[node] = size
        size += node.size_delta
        assert size >= 0

        jumps_to = list(node.get_jumps_to())
        if not jumps_to:
            return

        # avoid recursion in the common case because it could be slow
        node = jumps_to.pop()
        for other in jumps_to:
            _get_stack_sizes_to_dict(other, size, size_dict)


def get_stack_sizes(root_node: Node) -> typing.Dict[Node, int]:
    result: typing.Dict[Node, int] = {}
    _get_stack_sizes_to_dict(root_node, 0, result)
    return result


def get_max_stack_size(root_node: Node) -> int:
    return max(
        max(before, before + node.size_delta)
        for node, before in get_stack_sizes(root_node).items()
    )


# root_node does NOT have to be a Start node
# TODO: cache result somewhere, but careful with invalidation?
def get_all_nodes(root_node: Node) -> typing.Set[Node]:
    assert root_node is not None

    result = set()
    to_visit = {root_node}      # should be faster than recursion

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


def _graphviz_id(node: Node) -> str:
    return 'node' + str(id(node))


def _graphviz_code(
        root_node: Node,
        label_extra: str = '') -> typing.Iterator[str]:
    reachable = get_all_nodes(root_node)
    unreachable = _get_unreachable_nodes(reachable)
    assert not (reachable & unreachable)

    max_stack_size: typing.Union[str, int]
    try:
        max_stack_size = get_max_stack_size(root_node)
    except AssertionError:
        # get_max_stack_size will be called later as a part of the compilation,
        # and you will see the full traceback then
        max_stack_size = 'error'
    yield 'label="%s\\nmax stack size = %s";\n' % (label_extra, max_stack_size)

    for node in (reachable | unreachable):
        parts = [type(node).__name__]
        # TODO: display location somewhat nicely
        # .lineno attribute was replaced with .location attribute
#            if node.lineno is not None:
#                parts[0] += ', line %d' % node.lineno

        debug_string = _get_debug_string(node)
        if debug_string is not None:
            parts.append(debug_string)
        parts.append('size_delta=' + str(node.size_delta))
        parts.append('use_count=' + str(node.use_count))
        parts.append('id=%#x' % id(node))

        if node in unreachable:
            parts.append('UNREACHABLE')

        for to in node.get_jumps_to():
            if node not in (ref.objekt for ref in to.jumped_from):
                parts.append('HAS PROBLEMS with jumped_from stuff')

        yield '%s [label="%s"];\n' % (
            _graphviz_id(node), '\n'.join(parts).replace('"', r'\"'))

#        if isinstance(node, CreateFunction):
#            color = _random_color()
#            yield 'subgraph cluster%s {\n' % _graphviz_id(node)
#            yield 'style=filled;\n'
#            yield 'color="%s";\n' % color
#            yield from _graphviz_code(node.body_root_node, "FUNCTION BODY")
#            yield '}\n'
#            yield '%s [style=filled, fillcolor="%s"];' % (
#                _graphviz_id(node), color)

        if isinstance(node, TwoWayDecision):
            # color 'then' with green, 'otherwise' with red
            if node.then is not None:
                yield '%s -> %s [color=green]\n' % (
                    _graphviz_id(node), _graphviz_id(node.then))
            if node.otherwise is not None:
                yield '%s -> %s [color=red]\n' % (
                    _graphviz_id(node), _graphviz_id(node.otherwise))
        else:
            for to in node.get_jumps_to():
                yield '%s -> %s\n' % (_graphviz_id(node), _graphviz_id(to))


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
