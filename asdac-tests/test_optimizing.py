import pytest

from asdac import decision_tree, optimizer
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


def count_decisions(root_node):
    return sum(1 for node in decision_tree.get_all_nodes(root_node)
               if isinstance(node, decision_tree.BoolDecision))


def test_bool_constant_decisions_negation(compiler):
    root_node = compiler.create_tree('''
# may need to be replaced with something more complicated if optimizer gets
# better later
if 1 != 2:
    print("a")
else:
    print("b")
''')

    assert count_decisions(root_node) == 2
    optimizer.optimize(root_node, None)
    assert count_decisions(root_node) == 1
    # TODO: test content of resulting tree


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
    assert isinstance(next(nodes), decision_tree.StrConstant)       # "a"
    assert isinstance(next(nodes), decision_tree.PopOne)
    assert isinstance(next(nodes), decision_tree.GetBuiltinVar)     # print
    assert isinstance(next(nodes), decision_tree.StrConstant)       # "b"
    assert isinstance(next(nodes), decision_tree.CallFunction)
    assert no_more(nodes)


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


def test_function_bodies_get_optimized(compiler):
    start_node = compiler.create_tree('''
let f = (Bool b) -> Str:
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
