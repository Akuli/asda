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

import functools
import io
import random
import pathlib
import subprocess
import tempfile

from asdac import common, cooked_ast, utils


class Node:
    """
    size_delta tells how many objects this node pushes to the stack (positive)
    and pops from stack (negative). For example, if your function pops two
    objects, does something with them, and pushes the result to the stack, you
    should set size_delta to -2 + 1 = -1.

    use_count tells how many topmost objects of the stack this node uses. In
    the above example, it should be 2.
    """

    def __init__(self, *, use_count, size_delta, location=None):
        self.use_count = use_count
        self.size_delta = size_delta

        assert use_count >= 0
        if size_delta < 0:
            assert use_count >= abs(size_delta)

        # contains AttributeReferences
        # number of elements has nothing to do with the type of the node
        # more than 1 means e.g. beginning of loop, 0 means unreachable code
        self.jumped_from = set()

        # should be None for nodes created by the compiler
        self.location = location

    def get_jumps_to_including_nones(self):
        """Return iterable of nodes that may be ran after running this node.

        If execution (of the function or file) may end at this node, the
        resulting iterable contains one or more Nones.
        """
        raise NotImplementedError

    def get_jumps_to(self):
        """Return iterable of nodes that may be ran after running this node."""
        return (node for node in self.get_jumps_to_including_nones()
                if node is not None)

    def change_jump_to(self, ref, new):
        if ref.get() is not None:
            ref.get().jumped_from.remove(ref)

        ref.set(new)
        if new is not None:
            # can't jump to Start, avoids special cases
            # but you can jump to the node after the Start node
            assert not isinstance(ref.get(), Start)

            assert ref not in ref.get().jumped_from
            ref.get().jumped_from.add(ref)

    def __repr__(self):
        debug_string = _get_debug_string(self)
        if debug_string is None:
            return super().__repr__()
        return '<%s: %s>' % (type(self).__name__, debug_string)


# a node that can be used like:
#    something --> this node --> something
class PassThroughNode(Node):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.next_node = None

    def get_jumps_to_including_nones(self):
        return [self.next_node]

    def set_next_node(self, next_node):
        self.change_jump_to(
            utils.AttributeReference(self, 'next_node'), next_node)


# execution begins here, having this avoids weird special cases
class Start(PassThroughNode):

    def __init__(self, argvars, **kwargs):
        super().__init__(use_count=0, size_delta=len(argvars), **kwargs)
        self.argvars = argvars


class PushDummy(PassThroughNode):

    # the variable object is used for debugging and error messages
    def __init__(self, var, **kwargs):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.var = var


class GetBuiltinVar(PassThroughNode):

    def __init__(self, varname, **kwargs):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.varname = varname


class _BottomNode(PassThroughNode):

    # the var is used for debugging and error messages
    def __init__(self, index, var, **kwargs):
        super().__init__(**kwargs)
        self.index = index
        self.var = var


class SetToBottom(_BottomNode):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, use_count=1, size_delta=-1, **kwargs)


class GetFromBottom(_BottomNode):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, use_count=0, size_delta=1, **kwargs)


class PopOne(PassThroughNode):

    def __init__(self, *, is_popping_a_dummy=False, **kwargs):
        super().__init__(use_count=1, size_delta=-1, **kwargs)
        self.is_popping_a_dummy = is_popping_a_dummy


class Equal(PassThroughNode):

    def __init__(self, **kwargs):
        super().__init__(use_count=2, size_delta=-1, **kwargs)


class Plus(PassThroughNode):

    def __init__(self, **kwargs):
        super().__init__(use_count=2, size_delta=-1, **kwargs)


class Times(PassThroughNode):

    def __init__(self, **kwargs):
        super().__init__(use_count=2, size_delta=-1, **kwargs)


class GetAttr(PassThroughNode):

    def __init__(self, tybe, attrname, **kwargs):
        super().__init__(use_count=1, size_delta=0, **kwargs)
        self.tybe = tybe
        self.attrname = attrname


class StrConstant(PassThroughNode):

    def __init__(self, python_string, **kwargs):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.python_string = python_string


class IntConstant(PassThroughNode):

    def __init__(self, python_int, **kwargs):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.python_int = python_int


class CallFunction(PassThroughNode):

    def __init__(self, how_many_args, is_returning, **kwargs):
        use_count = 1 + how_many_args   # function object + arguments
        super().__init__(
            use_count=use_count,
            size_delta=(-use_count + int(bool(is_returning))),
            **kwargs)
        self.how_many_args = how_many_args


class CreateFunction(PassThroughNode):

    def __init__(self, functype, body_root_node, **kwargs):
        super().__init__(use_count=0, size_delta=1, **kwargs)
        self.functype = functype
        self.body_root_node = body_root_node


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
class StoreReturnValue(PassThroughNode):

    def __init__(self, **kwargs):
        super().__init__(use_count=1, size_delta=-1, **kwargs)


class StrJoin(PassThroughNode):

    def __init__(self, how_many_strings, **kwargs):
        super().__init__(
            use_count=how_many_strings, size_delta=(-how_many_strings + 1),
            **kwargs)
        self.how_many_strings = how_many_strings


class TwoWayDecision(Node):

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.then = None
        self.otherwise = None

    def get_jumps_to_including_nones(self):
        return [self.then, self.otherwise]

    def set_then(self, value):
        self.change_jump_to(
            utils.AttributeReference(self, 'then'), value)

    def set_otherwise(self, value):
        self.change_jump_to(
            utils.AttributeReference(self, 'otherwise'), value)


class BoolDecision(TwoWayDecision):

    def __init__(self, **kwargs):
        super().__init__(use_count=1, size_delta=-1, **kwargs)


def _get_debug_string(node):
    if isinstance(node, PushDummy):
        return node.var.name
    if isinstance(node, GetBuiltinVar):
        return node.varname
    if isinstance(node, (SetToBottom, GetFromBottom)):
        return 'varname %r, index %d' % (node.var.name, node.index)
    if isinstance(node, GetAttr):
        return node.tybe.name + '.' + node.attrname
    if isinstance(node, IntConstant):
        return str(node.python_int)
    if isinstance(node, StrConstant):
        return repr(node.python_string)
    if isinstance(node, CallFunction):
        n = node.how_many_args
        return '%d arg%s' % (n, 's' * int(n != 1))
    if isinstance(node, PopOne) and node.is_popping_a_dummy:
        return "is popping a dummy"
    return None


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
        size += node.size_delta
        assert size >= 0

        jumps_to = list(node.get_jumps_to())
        if not jumps_to:
            return

        # avoid recursion in the common case because it could be slow
        node = jumps_to.pop()
        for other in jumps_to:
            _get_stack_sizes_to_dict(other, size, size_dict)


def get_stack_sizes(root_node):
    result = {}
    _get_stack_sizes_to_dict(root_node, 0, result)
    return result


def get_max_stack_size(root_node):
    return max(
        max(before, before + node.size_delta)
        for node, before in get_stack_sizes(root_node).items()
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


# TODO: optimize this?
def get_unreachable_nodes(reachable_nodes: set):
    to_visit = reachable_nodes.copy()
    reachable_and_unreachable = set()

    while to_visit:
        node = to_visit.pop()
        if node in reachable_and_unreachable:
            continue

        reachable_and_unreachable.add(node)
        to_visit.update(ref.objekt for ref in node.jumped_from)

    return reachable_and_unreachable - reachable_nodes


def _random_color():
    rgb = (0, 0, 0)
    while sum(rgb)/len(rgb) < 0x80:   # too dark, create new color
        rgb = (random.randint(0x00, 0xff),
               random.randint(0x00, 0xff),
               random.randint(0x00, 0xff))
    return '#%02x%02x%02x' % rgb


def _graphviz_id(node):
    return 'node' + str(id(node))


def _graphviz_code(root_node, label_extra=''):
    reachable = get_all_nodes(root_node)
    unreachable = get_unreachable_nodes(reachable)
    assert not (reachable & unreachable)

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

        if node in unreachable:
            parts.append('UNREACHABLE')

        yield '%s [label="%s"];\n' % (
            _graphviz_id(node), '\n'.join(parts).replace('"', r'\"'))

        for to in node.get_jumps_to():
            assert node in (ref.objekt for ref in to.jumped_from)

        if isinstance(node, CreateFunction):
            color = _random_color()
            yield 'subgraph cluster%s {\n' % _graphviz_id(node)
            yield 'style=filled;\n'
            yield 'color="%s";\n' % color
            yield from _graphviz_code(node.body_root_node, "FUNCTION BODY")
            yield '}\n'
            yield '%s [style=filled, fillcolor="%s"];' % (
                _graphviz_id(node), color)

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
def graphviz(root_node, filename_without_ext):
    path = pathlib.Path(tempfile.gettempdir()) / 'asdac'
    path.mkdir(parents=True, exist_ok=True)
    png = path / (filename_without_ext + '.png')

    # overwrites the png file if it exists
    dot = subprocess.Popen(['dot', '-o', str(png), '-T', 'png'],
                           stdin=subprocess.PIPE)
    dot_stdin = io.TextIOWrapper(dot.stdin)
    dot_stdin.write('digraph {\n')
    dot_stdin.writelines(_graphviz_code(root_node))
    dot_stdin.write('}\n')
    dot_stdin.flush()
    dot_stdin.close()

    status = dot.wait()
    assert status == 0

    print("decision_tree.graphviz(): see", str(png))


# converts cooked ast to a decision tree
class _TreeCreator:

    def __init__(self, local_vars_level, local_vars_list, exit_points):
        # from now on, local variables are items in the beginning of the stack
        self.local_vars_level = local_vars_level
        self.local_vars_list = local_vars_list

        # .set_next_node methods that should be called to make stuff run every
        # time the function is about to early-return
        # used for cleaning up local variables from stack
        # not used in non-function tree creators
        self.exit_points = exit_points

        # why can't i assign in python lambda without dirty setattr haxor :(
        self.set_next_node = lambda node: setattr(self, 'root_node', node)
        self.root_node = None

    def subcreator(self):
        return _TreeCreator(
            self.local_vars_level, self.local_vars_list, self.exit_points)

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

    # inefficient, but gets optimized away
    def add_bool_negation(self):
        decision = BoolDecision()
        decision.set_then(GetBuiltinVar('FALSE'))
        decision.set_otherwise(GetBuiltinVar('TRUE'))
        self.set_next_node(decision)
        self.set_next_node = lambda node: (
            decision.then.set_next_node(node),
            decision.otherwise.set_next_node(node),
        )

    def _get_varlist_index(self, local_var: cooked_ast.Variable):
        assert local_var.level == self.local_vars_level
        if local_var not in self.local_vars_list:
            self.local_vars_list.append(local_var)
        return self.local_vars_list.index(local_var)

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
            if expression.var.level == self.local_vars_level:
                node = GetFromBottom(
                    self._get_varlist_index(expression.var), expression.var,
                    **boilerplate)
            elif expression.var.level == 0:
                node = GetBuiltinVar(expression.var.name, **boilerplate)
            else:
                print(expression.var)
                # closure variable
                raise NotImplementedError

            self.add_pass_through_node(node)

        elif isinstance(expression, (
                cooked_ast.Equal, cooked_ast.NotEqual,
                cooked_ast.Plus, cooked_ast.Times)):
            self.do_expression(expression.lhs)
            self.do_expression(expression.rhs)

            if isinstance(expression, cooked_ast.Equal):
                self.add_pass_through_node(Equal(**boilerplate))
            elif isinstance(expression, cooked_ast.NotEqual):
                self.add_pass_through_node(Equal(**boilerplate))
                self.add_bool_negation()
            elif isinstance(expression, cooked_ast.Plus):
                self.add_pass_through_node(Plus(**boilerplate))
            elif isinstance(expression, cooked_ast.Times):
                self.add_pass_through_node(Times(**boilerplate))
            else:
                raise RuntimeError("wat")

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

        # TODO: when closures work again, figure out how to do closures
        #       for arguments of the function
        elif isinstance(expression, cooked_ast.CreateFunction):
            creator = _TreeCreator(self.local_vars_level + 1,
                                   expression.argvars.copy(), [])
            creator.add_pass_through_node(Start(expression.argvars.copy()))
            creator.do_body(expression.body)
            creator.add_bottom_dummies()
            self.add_pass_through_node(CreateFunction(
                expression.type, creator.root_node, **boilerplate))

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
            if statement.var.level == self.local_vars_level:
                node = SetToBottom(
                    self._get_varlist_index(statement.var), statement.var,
                    **boilerplate)
            else:
                # closure variable
                raise NotImplementedError
            self.add_pass_through_node(node)

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
                creator.add_pass_through_node(GetBuiltinVar('TRUE'))
            else:
                creator.do_expression(statement.pre_cond)

            beginning_decision = BoolDecision(**boilerplate)
            creator.set_next_node(beginning_decision)
            creator.set_next_node = beginning_decision.set_then

            creator.do_body(statement.body)
            creator.do_body(statement.incr)

            if statement.post_cond is None:
                creator.add_pass_through_node(GetBuiltinVar('TRUE'))
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

        elif isinstance(statement, cooked_ast.Return):
            if statement.value is not None:
                self.do_expression(statement.value)
                self.add_pass_through_node(StoreReturnValue(**boilerplate))
            self.exit_points.append(self.set_next_node)
            self.set_next_node = lambda node: None

        else:
            assert False, type(statement)     # pragma: no cover

    def do_body(self, statements):
        for statement in statements:
            assert not isinstance(statement, list), statement
            self.do_statement(statement)

    def add_bottom_dummies(self):
        assert isinstance(self.root_node, Start)

        creator = self.subcreator()
        creator.add_pass_through_node(Start(self.root_node.argvars))

        for var in self.local_vars_list[len(self.root_node.argvars):]:
            creator.add_pass_through_node(PushDummy(var))

        if self.root_node.next_node is not None:
            creator.set_next_node(self.root_node.next_node)
            creator.set_next_node = self.set_next_node

        for index, var in enumerate(self.local_vars_list):
            pop = PopOne(is_popping_a_dummy=True)
            if index == 0:      # first time
                for func in creator.exit_points:
                    func(pop)
                creator.exit_points.clear()
            creator.add_pass_through_node(pop)

        # avoid creating an unreachable Start node
        # TODO: is this necessary?
        self.root_node.set_next_node(None)

        assert isinstance(creator.root_node, Start)
        self.root_node = creator.root_node
        self.set_next_node = creator.set_next_node


def create_tree(cooked_statements):
    tree_creator = _TreeCreator(1, [], [])
    tree_creator.add_pass_through_node(Start([]))
    tree_creator.do_body(cooked_statements)
    tree_creator.add_bottom_dummies()
    assert isinstance(tree_creator.root_node, Start)
    return tree_creator.root_node
