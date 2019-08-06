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

# most of the imports are for viewing this with graphviz while debugging
import bisect
import functools
import io
import pathlib
import subprocess
import tempfile
import threading
import time
from urllib.request import pathname2url
import webbrowser

from asdac import cooked_ast


class Node:

    def __init__(self, *, lineno=None):
        # the other of 'self -> other' is here
        # contains two elements for 'if' nodes
        # contains only one element for most things
        self.jumps_to = set()

        # number of elements has nothing to do with the type of the node
        # more than 1 means e.g. beginning of loop, 0 means dead code
        self.jumped_from = set()

        # how many objects this pushes to the stack (positive value) or pops
        # from the stack (negative value)
        #
        # override if needed
        #
        # this default is good for things like:
        #   - pop two things, do something, push result: -2 + 1 = -1
        #   - just pop off something
        self.push_count = -1

        # should be None for nodes created by the compiler
        self.lineno = lineno

    def add_jump_to(self, other):
        # TODO: what should this do when an if has same 'then' and 'otherwise'?
        assert other not in self.jumps_to

        # can't jump to Start, avoids special cases
        # but you can jump to the node after the Start node
        assert not isinstance(other, Start)

        self.jumps_to.add(other)
        other.jumped_from.add(self)

    def remove_jump_to(self, other):
        self.jumps_to.remove(other)
        other.jumped_from.remove(self)

    def change_jump_to(self, old, new):
        if old is not None:
            self.remove_jump_to(old)
        if new is not None:
            self.add_jump_to(new)

    def graphviz_string(self):
        return None

    # for debugging, displays a visual representation of the tree
    def graphviz(self):
        nodes = {}      # {node: id string}

        def recurser(node):
            if node not in nodes:
                nodes[node] = 'node' + str(len(nodes))
                for subnode in node.jumps_to:
                    recurser(subnode)

        recurser(self)

        path = pathlib.Path(tempfile.gettempdir()) / 'asdac'
        path.mkdir(parents=True, exist_ok=True)
        png = path / 'decision_tree.png'

        # overwrites the png file if it exists
        dot = subprocess.Popen(['dot', '-o', str(png), '-T', 'png'],
                               stdin=subprocess.PIPE)
        dot_stdin = io.TextIOWrapper(dot.stdin)
        dot_stdin.write('digraph {\n')

        try:
            max_stack_size = get_max_stack_size(self)
        except AssertionError:
            max_stack_size = 'error'    # lol

        dot_stdin.write(
            'label="\\nmax stack size = %s";\n' % max_stack_size)

        for node, id_string in nodes.items():
            parts = [type(node).__name__]
            if node.lineno is not None:
                parts[0] += ', line %d' % node.lineno
            if node.graphviz_string() is not None:
                parts.append(node.graphviz_string())
            parts.append('push_count=' + str(node.push_count))

            dot_stdin.write('%s [label="%s"];\n' % (
                id_string, '\n'.join(parts).replace('"', r'\"')))

            if isinstance(node, TwoWayDecision):
                # color 'then' with green, 'otherwise' with red
                if node.then is not None:
                    dot_stdin.write('%s -> %s [color=green]\n' % (
                        id_string, nodes[node.then]))
                if node.otherwise is not None:
                    dot_stdin.write('%s -> %s [color=red]\n' % (
                        id_string, nodes[node.otherwise]))
            else:
                for to in node.jumps_to:
                    dot_stdin.write('%s -> %s\n' % (
                        id_string, nodes[to]))

        dot_stdin.write('}\n')
        dot_stdin.flush()
        dot_stdin.close()

        status = dot.wait()
        assert status == 0

        webbrowser.open('file://' + pathname2url(str(png)))


# if we have (in graphviz syntax) a->c->d->f->g, b->e->f->g
# then find_merge(a, b) returns f, because that's first node where they merge
# may return None, if paths never merge together
# see tests for corner cases
#
# TODO: better algorithm? i found this
# https://www.hackerrank.com/topics/lowest-common-ancestor
# but doesn't seem to handle cyclic graphs?
def find_merge(a: Node, b: Node):
    assert a is not None
    assert b is not None

    reachable_from_a = {a}
    reachable_from_b = {b}

    while True:
        try:
            return (reachable_from_a & reachable_from_b).pop()
        except KeyError:
            pass

        did_something = False
        for reaching_set in [reachable_from_a, reachable_from_b]:
            for node in reaching_set.copy():
                for other_node in node.jumps_to:
                    if other_node not in reaching_set:
                        reaching_set.add(other_node)
                        did_something = True

        if not did_something:
            return None


# a node that can be used like:
#    something --> this node --> something
class PassThroughNode(Node):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_node = None

    def set_next_node(self, next_node):
        self.change_jump_to(self.next_node, next_node)
        self.next_node = next_node


# execution begins here, having this avoids weird special cases
class Start(PassThroughNode):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.push_count = 0


class _SetOrGetVar(PassThroughNode):

    def __init__(self, var, **kwargs):
        super().__init__(**kwargs)
        self.var = var

    def graphviz_string(self):
        return self.var.name


class SetVar(_SetOrGetVar):
    pass


class GetVar(_SetOrGetVar):

    def __init__(self, var, **kwargs):
        super().__init__(var, **kwargs)
        self.push_count = 1


class PopOne(PassThroughNode):
    pass


class Equal(PassThroughNode):
    pass


class Plus(PassThroughNode):
    pass


class GetAttr(PassThroughNode):

    def __init__(self, tybe, attrname, **kwargs):
        super().__init__(**kwargs)
        self.tybe = tybe
        self.attrname = attrname
        self.push_count = 0

    def graphviz_string(self):
        return self.tybe.name + '.' + self.attrname


class StrConstant(PassThroughNode):

    def __init__(self, python_string, **kwargs):
        super().__init__(**kwargs)
        self.python_string = python_string
        self.push_count = 1

    def graphviz_string(self):
        return repr(self.python_string)


class IntConstant(PassThroughNode):

    def __init__(self, python_int, **kwargs):
        super().__init__(**kwargs)
        self.python_int = python_int
        self.push_count = 1

    def graphviz_string(self):
        return str(self.python_int)


class CallFunction(PassThroughNode):

    def __init__(self, how_many_args, is_returning, **kwargs):
        super().__init__(**kwargs)
        self.how_many_args = how_many_args
        self.push_count = (
            -1                          # function object
            - how_many_args             # arguments
            + int(bool(is_returning))   # return value, if any
        )

    def graphviz_string(self):
        return ('1 arg' if self.how_many_args == 1 else
                '%d args' % self.how_many_args)


class StrJoin(PassThroughNode):

    def __init__(self, how_many_strings, **kwargs):
        super().__init__(**kwargs)
        self.how_many_strings = how_many_strings
        self.push_count = -how_many_strings + 1


class TwoWayDecision(Node):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.then = None
        self.otherwise = None

    def set_then(self, value):
        self.change_jump_to(self.then, value)
        self.then = value

    def set_otherwise(self, value):
        self.change_jump_to(self.otherwise, value)
        self.otherwise = value


class BoolDecision(TwoWayDecision):
    pass


# converts cooked ast to a decision tree
class _TreeCreator:

    def __init__(self, compilation, line_start_offsets):
        self.root_node = None
        # why can't i assign in python lambda without dirty setattr haxor :(
        self.set_next_node = lambda node: setattr(self, 'root_node', node)
        self.compilation = compilation
        self.line_start_offsets = line_start_offsets

    def subcreator(self):
        return _TreeCreator(self.compilation, self.line_start_offsets)

    def add_pass_through_node(self, node):
        assert isinstance(node, PassThroughNode)
        self.set_next_node(node)
        self.set_next_node = node.set_next_node

    # returns line number so that 1 means first line
    def _lineno(self, location):
        #    >>> offsets = [0, 4, 10]
        #    >>> bisect.bisect(offsets, 0)
        #    1
        #    >>> bisect.bisect(offsets, 3)
        #    1
        #    >>> bisect.bisect(offsets, 4)
        #    2
        #    >>> bisect.bisect(offsets, 8)
        #    2
        #    >>> bisect.bisect(offsets, 9)
        #    2
        #    >>> bisect.bisect(offsets, 10)
        #    3
        assert location.compilation == self.compilation
        return bisect.bisect(self.line_start_offsets, location.offset)

    def do_function_call(self, call):
        self.do_expression(call.function)
        for arg in call.args:
            self.do_expression(arg)

        self.add_pass_through_node(CallFunction(
            len(call.args), (call.function.type.returntype is not None),
            lineno=self._lineno(call.location)))

    # inefficient, but there will be optimizers later i think
    def add_bool_negation(self):
        decision = BoolDecision()
        decision.set_then(GetVar(cooked_ast.BUILTIN_VARS['FALSE']))
        decision.set_otherwise(GetVar(cooked_ast.BUILTIN_VARS['TRUE']))
        self.set_next_node(decision)
        self.set_next_node = lambda node: (
            decision.then.set_next_node(node),
            decision.otherwise.set_next_node(node),
        )

    def do_expression(self, expression):
        assert expression.type is not None
        boilerplate = {'lineno': self._lineno(expression.location)}

        if isinstance(expression, cooked_ast.StrConstant):
            self.add_pass_through_node(StrConstant(
                expression.python_string, **boilerplate))

        elif isinstance(expression, cooked_ast.IntConstant):
            self.add_pass_through_node(IntConstant(
                expression.python_int, **boilerplate))

        elif isinstance(expression, cooked_ast.GetVar):
            self.add_pass_through_node(GetVar(
                expression.var, **boilerplate))

        elif isinstance(expression, (cooked_ast.Equal, cooked_ast.NotEqual)):
            self.do_expression(expression.lhs)
            self.do_expression(expression.rhs)
            self.add_pass_through_node(Equal(**boilerplate))
            if isinstance(expression, cooked_ast.NotEqual):
                self.add_bool_negation()

        elif isinstance(expression, cooked_ast.Plus):
            self.do_expression(expression.lhs)
            self.do_expression(expression.rhs)
            self.add_pass_through_node(Plus(**boilerplate))

        elif isinstance(expression, cooked_ast.StrJoin):
            for part in expression.parts:
                self.do_expression(part)
            self.add_pass_through_node(StrJoin(len(expression.parts)))

        elif isinstance(expression, cooked_ast.CallFunction):
            self.do_function_call(expression)

        elif isinstance(expression, cooked_ast.GetAttr):
            self.do_expression(expression.obj)
            self.add_pass_through_node(GetAttr(
                expression.obj.type, expression.attrname))

        else:
            assert False, expression    # pragma: no cover

    def do_statement(self, statement):
        boilerplate = {'lineno': self._lineno(statement.location)}

        if isinstance(statement, cooked_ast.CreateLocalVar):
            pass

        elif isinstance(statement, cooked_ast.CallFunction):
            self.do_function_call(statement)
            if statement.type is not None:
                # not a void function, ignore return value
                self.add_pass_through_node(PopOne(**boilerplate))

        elif isinstance(statement, cooked_ast.SetVar):
            self.do_expression(statement.value)
            self.add_pass_through_node(SetVar(statement.var, **boilerplate))

        elif isinstance(statement, cooked_ast.IfStatement):
            self.do_expression(statement.cond)
            result = BoolDecision(**boilerplate)

            if_creator = self.subcreator()
            if_creator.set_next_node = result.set_then
            if_creator.do_body(statement.if_body)

            else_creator = self.subcreator()
            else_creator.set_next_node = result.set_otherwise
            else_creator.do_body(statement.else_body)

            self.set_next_node(result)
            self.set_next_node = lambda next_node: (
                if_creator.set_next_node(next_node),
                else_creator.set_next_node(next_node),
            )

        elif isinstance(statement, cooked_ast.Loop):
            creator = self.subcreator()
            if statement.pre_cond is None:
                creator.add_pass_through_node(GetVar(
                    cooked_ast.BUILTIN_VARS['TRUE']))
            else:
                creator.do_expression(statement.pre_cond)

            beginning_decision = BoolDecision(**boilerplate)
            creator.set_next_node(beginning_decision)
            creator.set_next_node = beginning_decision.set_then

            creator.do_body(statement.body)
            creator.do_body(statement.incr)

            if statement.post_cond is None:
                creator.add_pass_through_node(GetVar(
                    cooked_ast.BUILTIN_VARS['TRUE']))
            else:
                creator.do_expression(statement.post_cond)

            end_decision = BoolDecision(**boilerplate)
            end_decision.set_then(creator.root_node)
            creator.set_next_node(end_decision)

            self.set_next_node(creator.root_node)
            self.set_next_node = lambda node: (
                beginning_decision.set_otherwise(node),
                end_decision.set_otherwise(node),
            )

        else:
            assert False, type(statement)     # pragma: no cover

    def do_body(self, statements):
        for statement in statements:
            assert not isinstance(statement, list), statement
            self.do_statement(statement)


def _combine_nodes(lizt):
    for first, second in zip(lizt, lizt[1:]):
        first.set_next_node(second)
    return lizt[0] if lizt else None


# size_dict is like this {node: stack size BEFORE running the node}
def _get_stack_sizes_to_dict(node, size, size_dict):
    assert node is not None

    while True:
        if node in size_dict:
            assert size == size_dict[node]
            return

        size_dict[node] = size
        size += node.push_count
        assert size >= 0

        if not node.jumps_to:
            return

        # avoid recursion in the common case because it could be slow
        [node, *other_nodes] = node.jumps_to
        for other in other_nodes:
            _get_stack_sizes_to_dict(other, size, size_dict)


def get_max_stack_size(node):
    if node is None:
        return 0

    size_dict = {}
    _get_stack_sizes_to_dict(node, 0, size_dict)
    return max(
        max(before, before + node.push_count)
        for node, before in size_dict.items()
    )


def create_tree(compilation, cooked_statements, source_code):
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    start = Start()

    tree_creator = _TreeCreator(compilation, line_start_offsets)
    tree_creator.set_next_node(start)
    tree_creator.set_next_node = start.set_next_node
    tree_creator.do_body(cooked_statements)
    assert tree_creator.root_node is start
    return start
