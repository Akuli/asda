# FIXME: update xfailing tests

import pytest

from asdac import cooked_ast, decision_tree, objects, optimizer
from asdac.common import CompileError


def iterate_passthroughnodes(node):
    while node is not None:
        if not isinstance(node, decision_tree.PassThroughNode):
            raise RuntimeError
        yield node
        node = node.next_node


def contains_only_passthroughnodes(node):
    try:
        for node in iterate_passthroughnodes(node):
            pass
        return True
    except RuntimeError:
        return False


def no_more(iterator):
    try:
        next(iterator)
        return False
    except StopIteration:
        return True


def test_bool_constant_decisions_do_while_false(compiler):
    root_node = compiler.create_tree('''
do:
    print("loop")
while FALSE
print("done")
''')

    assert not contains_only_passthroughnodes(root_node)
    optimizer.optimize(root_node, None)
    assert contains_only_passthroughnodes(root_node)

    nodes = iterate_passthroughnodes(root_node)
    assert isinstance(next(nodes), decision_tree.Start)

    assert isinstance(next(nodes), decision_tree.GetBuiltinVar)  # print
    assert isinstance(next(nodes), decision_tree.StrConstant)    # "loop"
    assert isinstance(next(nodes), decision_tree.CallFunction)

    assert isinstance(next(nodes), decision_tree.GetBuiltinVar)  # print
    assert isinstance(next(nodes), decision_tree.StrConstant)    # "done"
    assert isinstance(next(nodes), decision_tree.CallFunction)

    assert no_more(nodes)


def test_bool_constant_decisions_while_false(compiler):
    root_node = compiler.create_tree('''
while FALSE:
    print("stuff")
''')

    assert not contains_only_passthroughnodes(root_node)
    optimizer.optimize(root_node, None)
    assert contains_only_passthroughnodes(root_node)

    nodes = iterate_passthroughnodes(root_node)
    assert isinstance(next(nodes), decision_tree.Start)
    assert no_more(nodes)


def test_bool_constant_decisions_while_true(compiler):
    root_node = compiler.create_tree('''
while TRUE:
    print("stuff")
''')

    assert not contains_only_passthroughnodes(root_node)
    optimizer.optimize(root_node, None)
    # contains_only_passthroughnodes would go into infinite loop now

    nodes = iterate_passthroughnodes(root_node)     # infinite iterator
    assert isinstance(next(nodes), decision_tree.Start)

    for ever in range(123):
        assert isinstance(next(nodes), decision_tree.GetBuiltinVar)  # print
        assert isinstance(next(nodes), decision_tree.StrConstant)    # "stuff"
        assert isinstance(next(nodes), decision_tree.CallFunction)


@pytest.mark.xfail
def test_useless_variable(compiler, capsys):
    root_node = compiler.create_tree('''
let garbage = "a"
print("b")
''')
    assert capsys.readouterr() == ('', '')

    optimizer.optimize(root_node, None)
    assert capsys.readouterr() == (
        "warning: value of variable 'garbage' is set, but never used\n", '')

    nodes = iterate_passthroughnodes(root_node)

    # gets rid of everything related to 'garbage'
    # TODO: should also get rid of all of "a"
    assert isinstance(next(nodes), decision_tree.Start)
    assert isinstance(next(nodes), decision_tree.GetBuiltinVar)     # print
    assert isinstance(next(nodes), decision_tree.StrConstant)       # "b"
    assert isinstance(next(nodes), decision_tree.CallFunction)
    assert no_more(nodes)


@pytest.mark.xfail
def test_variable_used_right_away(compiler):
    root_node = compiler.create_tree('''
let one = 1
let two = one + 1
let three = two + 1
print(three.to_string())
''')
    optimizer.optimize(root_node, None)

    # 'one' and 'two' should get optimized away
    #
    # currently 'three' doesn't get optimized, because print must be pushed
    # before it
    nodes = iterate_passthroughnodes(root_node)
    assert isinstance(next(nodes), decision_tree.Start)
    assert isinstance(next(nodes), decision_tree.PushDummy)      # three
    assert isinstance(next(nodes), decision_tree.IntConstant)    # 1
    assert isinstance(next(nodes), decision_tree.IntConstant)    # 1
    assert isinstance(next(nodes), decision_tree.Plus)           # +
    assert isinstance(next(nodes), decision_tree.IntConstant)    # 1
    assert isinstance(next(nodes), decision_tree.Plus)           # +
    assert isinstance(next(nodes), decision_tree.SetToBottom)    # three
    assert isinstance(next(nodes), decision_tree.GetBuiltinVar)  # print
    assert isinstance(next(nodes), decision_tree.GetFromBottom)  # three
    assert isinstance(next(nodes), decision_tree.GetAttr)        # .to_string
    assert isinstance(next(nodes), decision_tree.CallFunction)   # ()
    assert isinstance(next(nodes), decision_tree.CallFunction)   # print(...)
    assert isinstance(next(nodes), decision_tree.PopOne)         # three
    assert no_more(nodes)


@pytest.mark.xfail
def test_function_bodies_get_optimized(compiler):
    start_node = compiler.create_tree('''
let f = (Bool b) -> void:
    while TRUE:
        print("I'll never return haha")
''')
    optimizer.optimize(start_node, None)
    [createfunc] = (node for node in decision_tree.get_all_nodes(start_node)
                    if isinstance(node, decision_tree.CreateFunction))

    nodes = iterate_passthroughnodes(createfunc.body_root_node)
    assert isinstance(next(nodes), decision_tree.Start)

    for ever in range(123):
        assert isinstance(next(nodes), decision_tree.GetBuiltinVar)  # print
        assert isinstance(next(nodes), decision_tree.StrConstant)
        assert isinstance(next(nodes), decision_tree.CallFunction)


def _count_decisions(root_node):
    return sum(1 for node in decision_tree.get_all_nodes(root_node)
               if isinstance(node, decision_tree.TwoWayDecision))


def _find_merge_after_decision(start_node):
    [decision] = (node for node in decision_tree.get_all_nodes(start_node)
                  if isinstance(node, decision_tree.TwoWayDecision))
    return decision_tree.find_merge([decision.then, decision.otherwise])


def test_similar_nodes(compiler):
    start_node = compiler.create_tree('''
if 1 + 1 == 2:
    print("A")
else:
    print("B")
print("C")
''')
    assert _count_decisions(start_node) == 2

    optimizer.optimize(start_node, None)
    assert _count_decisions(start_node) == 1
    common_to_print_a_and_b = _find_merge_after_decision(start_node)
    assert isinstance(common_to_print_a_and_b, decision_tree.CallFunction)


def test_function_doesnt_return_a_value_error(compiler):
    root_node = compiler.create_tree('''
let f = (Bool b) -> Str:
    if b:
        return "Yay"
''')
    with pytest.raises(CompileError) as e:
        optimizer.optimize(root_node, None)
    assert e.value.message == (
        "this function should return a value in all cases, "
        "but seems like it doesn't")

    optimizer.optimize(compiler.create_tree('''
let f = (Bool b) -> Str:
    if b:
        return "Yay"
    else:
        return "Nay"
'''), None)

    optimizer.optimize(compiler.create_tree('''
let f = (Bool b) -> Str:
    if b:
        return "Yay"
    return "Nay"
'''), None)

    optimizer.optimize(compiler.create_tree('''
let f = (Bool b) -> Str:
    if TRUE:
        return "Yay"
'''), None)

    optimizer.optimize(compiler.create_tree('''
let f = (Bool b) -> Str:
    while TRUE:
        print("I'll never return haha")
'''), None)


def test_variable_not_set_error(compiler):
    root_node = compiler.create_tree('''
let f = (Bool b) -> void:
    if b:
        outer let wat = "waaaat"
    print(wat)
''')
    with pytest.raises(CompileError) as e:
        optimizer.optimize(root_node, None)
    assert e.value.message == "variable 'wat' might not be set"

    root_node = compiler.create_tree('''
let f = (Str s) -> void:
    if TRUE:
        outer let wat = "waaaat"
    print(wat)
    print(s)
''')
    optimizer.optimize(root_node, None)


@pytest.mark.xfail
def test_booldecision_before_truefalse(compiler):
    start_node = compiler.create_tree('''
let and = (Bool a, Bool b) -> Bool:
    if a:
        if b:
            return TRUE
    return FALSE
''')
    optimizer.optimize(start_node, None)
    and_start = start_node.next_node.body_root_node

    #     Start
    #       |
    #       a
    #       |
    #  BoolDecision
    #  yes/     \no
    #    /       \
    #   b      FALSE
    #    \     /
    #     \   /
    # StoreReturnValue
    #       |
    #      ...

    assert isinstance(and_start, decision_tree.Start)
    assert isinstance(and_start.next_node, decision_tree.GetFromBottom)
    decision = and_start.next_node.next_node

    assert isinstance(decision, decision_tree.BoolDecision)
    assert isinstance(decision.then, decision_tree.GetFromBottom)
    assert isinstance(decision.otherwise, decision_tree.GetBuiltinVar)
    assert decision.otherwise.varname == 'FALSE'

    assert isinstance(decision.then.next_node, decision_tree.StoreReturnValue)
    assert decision.then.next_node is decision.otherwise.next_node


def test_popone():
    variable = cooked_ast.Variable('x', objects.BUILTIN_TYPES['Str'], None, 1)
    start = decision_tree.Start([])
    nodes = iterate_passthroughnodes(start)
    next(nodes).set_next_node(decision_tree.CreateBox(variable))
    next(nodes).set_next_node(decision_tree.UnBox())
    next(nodes).set_next_node(decision_tree.PopOne())

    assert start.next_node.next_node.next_node.next_node is None
    assert optimizer.popone._skip_unnecessary_nodes(start.next_node.next_node)
    assert start.next_node.next_node.next_node is None
    assert optimizer.popone._skip_unnecessary_nodes(start.next_node)
    assert start.next_node is None

    start = decision_tree.Start([])
    nodes = iterate_passthroughnodes(start)
    next(nodes).set_next_node(decision_tree.IntConstant(1))
    next(nodes).set_next_node(decision_tree.IntConstant(2))
    next(nodes).set_next_node(decision_tree.Plus())
    next(nodes).set_next_node(decision_tree.PopOne())

    optimizer.optimize(start, None)
    assert start.next_node is None
