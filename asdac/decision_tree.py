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
        self.push_count = 0

        # should be None for nodes created by the compiler
        self.lineno = lineno

    def add_jump_to(self, other):
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

        for node, id_string in nodes.items():
            parts = [type(node).__name__]
            if node.lineno is not None:
                parts[0] += ', line %d' % node.lineno
            if node.graphviz_string() is not None:
                parts.append(node.graphviz_string())
            parts.append('push_count=' + str(node.push_count))

            dot_stdin.write('%s [label="%s"];\n' % (
                id_string, '\n'.join(parts).replace('"', r'\"')))

            for to in node.jumps_to:
                dot_stdin.write('%s -> %s\n' % (
                    id_string, nodes[to]))

        dot_stdin.write('}\n')
        dot_stdin.flush()
        dot_stdin.close()

        status = dot.wait()
        assert status == 0

        webbrowser.open('file://' + pathname2url(str(png)))


# a node that can be used like:
#    something --> this node --> something
class PassThroughNode(Node):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_node = None

    def set_next_node(self, next_node):
        self.change_jump_to(self.next_node, next_node)
        self.next_node = next_node


class _SetOrGetVar(PassThroughNode):

    def __init__(self, var, **kwargs):
        super().__init__(**kwargs)
        self.var = var

    def graphviz_string(self):
        return repr(self.var.name)


class SetVar(_SetOrGetVar):

    def __init__(self, var, **kwargs):
        super().__init__(var, **kwargs)
        self.push_count = -1


class GetVar(_SetOrGetVar):

    def __init__(self, var, **kwargs):
        super().__init__(var, **kwargs)
        self.push_count = 1


class StrConstant(PassThroughNode):

    def __init__(self, python_string, **kwargs):
        super().__init__(**kwargs)
        self.python_string = python_string
        self.push_count = 1

    def graphviz_string(self):
        return repr(self.python_string)


class CallFunction(PassThroughNode):

    def __init__(self, how_many_args, is_returning, **kwargs):
        super().__init__(**kwargs)
        self.how_many_args = how_many_args
        print(is_returning)
        self.push_count = (
            -1                          # function object
            - how_many_args             # arguments
            + int(bool(is_returning))   # return value, if any
        )

    def graphviz_string(self):
        return ('1 arg' if self.how_many_args == 1 else
                '%d args' % self.how_many_args)


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

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.push_count = -1  # pops a bool object from the stack


# converts cooked ast to a decision tree
class _TreeCreator:

    def __init__(self, compilation, line_start_offsets):
        self.results = []
        self.compilation = compilation
        self.line_start_offsets = line_start_offsets

    def subcreator(self):
        return _TreeCreator(self.compilation, self.line_start_offsets)

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
        self.results.append(CallFunction(
            len(call.args), (call.function.type.returntype is not None),
            lineno=self._lineno(call.location)))

    def attrib_index(self, tybe, name):
        assert isinstance(tybe.attributes, collections.OrderedDict)
        return list(tybe.attributes.keys()).index(name)

    def do_expression(self, expression):
        boilerplate = {'lineno': self._lineno(expression.location)}

        if isinstance(expression, cooked_ast.StrConstant):
            self.results.append(StrConstant(
                expression.python_string, **boilerplate))

        elif isinstance(expression, cooked_ast.GetVar):
            self.results.append(GetVar(expression.var, **boilerplate))

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
                self.results.append(PopOne(**boilerplate))

        elif isinstance(statement, cooked_ast.SetVar):
            self.do_expression(statement.value)
            self.results.append(SetVar(statement.var, **boilerplate))

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


def create_tree(compilation, cooked_statements, source_code):
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    builtin_tree_creator = _TreeCreator(compilation, line_start_offsets)
    file_tree_creator = builtin_tree_creator.subcreator()

    file_tree_creator.do_body(cooked_statements)
    return _combine_nodes(file_tree_creator.results)
