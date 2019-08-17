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

from asdac import cooked_ast, utils


class Node:

    def __init__(self, *, location=None):
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
        self.location = location

    def get_jumps_to(self):
        raise NotImplementedError

    def change_jump_to(self, ref, new):
        if ref.get() is not None:
            ref.get().jumped_from.remove(ref)

        ref.set(new)
        if new is not None:
            # can't jump to Start, avoids special cases
            # but you can jump to the node after the Start node
            assert not isinstance(ref.get(), Start)
            ref.get().jumped_from.add(ref)

    # for debugging
    def graphviz_string(self):
        return None

    def __repr__(self):
        result = type(self).__name__

        graphviz_string = self.graphviz_string()
        if graphviz_string is not None:
            result += ': ' + graphviz_string

        return '<' + result + '>'


# a node that can be used like:
#    something --> this node --> something
class PassThroughNode(Node):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_node = None

    def get_jumps_to(self):
        if self.next_node is not None:
            yield self.next_node

    def set_next_node(self, next_node):
        self.change_jump_to(
            utils.AttributeReference(self, 'next_node'), next_node)


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

    def get_jumps_to(self):
        if self.then is not None:
            yield self.then
        if self.otherwise is not None:
            yield self.otherwise

    def set_then(self, value):
        self.change_jump_to(
            utils.AttributeReference(self, 'then'), value)

    def set_otherwise(self, value):
        self.change_jump_to(
            utils.AttributeReference(self, 'otherwise'), value)


class BoolDecision(TwoWayDecision):
    pass


# to use this, create the new node and set its .next_node or similar
# then call this function
def replace_node(old: Node, new: Node):
    if new is not None:
        new.jumped_from.update(old.jumped_from)

    for ref in old.jumped_from:
        ref.set(new)


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

        jumps_to = list(node.get_jumps_to())
        if not jumps_to:
            return

        # avoid recursion in the common case because it could be slow
        [node, *other_nodes] = jumps_to
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


def _items_in_all_sets(sets):
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
def find_merge(nodes, callback=(lambda node: node.get_jumps_to())):
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
def get_all_nodes(root_node):
    assert root_node is not None

    result = set()
    to_visit = {root_node}      # should be faster than recursion

    while to_visit:
        node = to_visit.pop()
        if node not in result:
            result.add(node)
            to_visit.update(node.get_jumps_to())

    return result


# for debugging, displays a visual representation of the tree
def graphviz(root_node, filename_without_ext):
    nodes = {node: 'node' + str(number)
             for number, node in enumerate(get_all_nodes(root_node))}

    path = pathlib.Path(tempfile.gettempdir()) / 'asdac'
    path.mkdir(parents=True, exist_ok=True)
    png = path / (filename_without_ext + '.png')

    # overwrites the png file if it exists
    dot = subprocess.Popen(['dot', '-o', str(png), '-T', 'png'],
                           stdin=subprocess.PIPE)
    dot_stdin = io.TextIOWrapper(dot.stdin)
    dot_stdin.write('digraph {\n')

    try:
        max_stack_size = get_max_stack_size(root_node)
    except AssertionError:
        # get_max_stack_size will be called later as a part of the compilation,
        # and you will see the full traceback then
        max_stack_size = 'error'

    dot_stdin.write(
        'label="\\nmax stack size = %s";\n' % max_stack_size)

    for node in nodes:
        parts = [type(node).__name__]
        # TODO: display location somewhat nicely
        # .lineno attribute was replaced with .location attribute
#            if node.lineno is not None:
#                parts[0] += ', line %d' % node.lineno
        if node.graphviz_string() is not None:
            parts.append(node.graphviz_string())
        parts.append('push_count=' + str(node.push_count))

        dot_stdin.write('%s [label="%s"];\n' % (
            nodes[node], '\n'.join(parts).replace('"', r'\"')))

        for to in node.get_jumps_to():
            assert node in (ref.objekt for ref in to.jumped_from)

        if isinstance(node, TwoWayDecision):
            # color 'then' with green, 'otherwise' with red
            if node.then is not None:
                dot_stdin.write('%s -> %s [color=green]\n' % (
                    nodes[node], nodes[node.then]))
            if node.otherwise is not None:
                dot_stdin.write('%s -> %s [color=red]\n' % (
                    nodes[node], nodes[node.otherwise]))
        else:
            for to in node.get_jumps_to():
                dot_stdin.write('%s -> %s\n' % (
                    nodes[node], nodes[to]))

    dot_stdin.write('}\n')
    dot_stdin.flush()
    dot_stdin.close()

    status = dot.wait()
    assert status == 0

    print("decision_tree.graphviz(): see", str(png))


# converts cooked ast to a decision tree
class _TreeCreator:

    def __init__(self):
        self.root_node = None
        # why can't i assign in python lambda without dirty setattr haxor :(
        self.set_next_node = lambda node: setattr(self, 'root_node', node)

    def add_pass_through_node(self, node):
        assert isinstance(node, PassThroughNode)
        self.set_next_node(node)
        self.set_next_node = node.set_next_node

    def do_function_call(self, call):
        self.do_expression(call.function)
        for arg in call.args:
            self.do_expression(arg)

        self.add_pass_through_node(CallFunction(
            len(call.args), (call.function.type.returntype is not None),
            location=call.location))

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
        boilerplate = {'location': expression.location}

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
        boilerplate = {'location': statement.location}

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

            if_creator = _TreeCreator()
            if_creator.set_next_node = result.set_then
            if_creator.do_body(statement.if_body)

            else_creator = _TreeCreator()
            else_creator.set_next_node = result.set_otherwise
            else_creator.do_body(statement.else_body)

            self.set_next_node(result)
            self.set_next_node = lambda next_node: (
                if_creator.set_next_node(next_node),
                else_creator.set_next_node(next_node),
            )

        elif isinstance(statement, cooked_ast.Loop):
            creator = _TreeCreator()
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


def create_tree(cooked_statements):
    start = Start()

    tree_creator = _TreeCreator()
    tree_creator.set_next_node(start)
    tree_creator.set_next_node = start.set_next_node
    tree_creator.do_body(cooked_statements)
    assert tree_creator.root_node is start
    return start
