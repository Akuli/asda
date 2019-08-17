import pytest

from asdac import decision_tree, optimizer


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
    optimizer.optimize(root_node)
    assert contains_only_passthroughnodes(root_node)

    nodes = iterate_passthroughnodes(root_node)
    assert isinstance(next(nodes), decision_tree.Start)

    assert isinstance(next(nodes), decision_tree.GetVar)        # print
    assert isinstance(next(nodes), decision_tree.StrConstant)   # "loop"
    assert isinstance(next(nodes), decision_tree.CallFunction)

    assert isinstance(next(nodes), decision_tree.GetVar)        # print
    assert isinstance(next(nodes), decision_tree.StrConstant)   # "done"
    assert isinstance(next(nodes), decision_tree.CallFunction)

    assert no_more(nodes)


def test_bool_constant_decisions_while_false(compiler):
    root_node = compiler.create_tree('''
while FALSE:
    print("stuff")
''')

    assert not contains_only_passthroughnodes(root_node)
    optimizer.optimize(root_node)
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
    optimizer.optimize(root_node)
    # contains_only_passthroughnodes would go into infinite loop

    nodes = iterate_passthroughnodes(root_node)     # infinite iterator
    assert isinstance(next(nodes), decision_tree.Start)

    for ever in range(123):
        assert isinstance(next(nodes), decision_tree.GetVar)        # print
        assert isinstance(next(nodes), decision_tree.StrConstant)   # "stuff"
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
    optimizer.optimize(root_node)
    assert count_decisions(root_node) == 1
    # TODO: test content of resulting tree


def test_useless_variable(compiler, capsys):
    root_node = compiler.create_tree('''
let garbage = "a"
print("b")
''')
    assert capsys.readouterr() == ('', '')

    optimizer.optimize(root_node)
    assert capsys.readouterr() == (
        "warning: value of variable 'garbage' is set, but never used\n", '')

    # TODO: should get rid of all of "a"
    nodes = iterate_passthroughnodes(root_node)

    assert isinstance(next(nodes), decision_tree.Start)
    assert isinstance(next(nodes), decision_tree.StrConstant)   # "a"
    assert isinstance(next(nodes), decision_tree.PopOne)
    assert isinstance(next(nodes), decision_tree.GetVar)        # print
    assert isinstance(next(nodes), decision_tree.StrConstant)   # "b"
    assert isinstance(next(nodes), decision_tree.CallFunction)
    assert no_more(nodes)


def test_used_right_away(compiler, capsys):
    root_node = compiler.create_tree('''
let one = 1
let two = one + 1
let three = two + 1
print(three.to_string())
''')

    nodes = iterate_passthroughnodes(root_node)
    assert isinstance(next(nodes), decision_tree.Start)
    assert isinstance(next(nodes), decision_tree.IntConstant)   # 1
    assert isinstance(next(nodes), decision_tree.SetVar)        # one
    assert isinstance(next(nodes), decision_tree.GetVar)        # one
    assert isinstance(next(nodes), decision_tree.IntConstant)   # 1
    assert isinstance(next(nodes), decision_tree.Plus)          # +
    assert isinstance(next(nodes), decision_tree.SetVar)        # two
    assert isinstance(next(nodes), decision_tree.GetVar)        # two
    assert isinstance(next(nodes), decision_tree.IntConstant)   # 1
    assert isinstance(next(nodes), decision_tree.Plus)          # +
    assert isinstance(next(nodes), decision_tree.SetVar)        # three
    assert isinstance(next(nodes), decision_tree.GetVar)        # print
    assert isinstance(next(nodes), decision_tree.GetVar)        # three
    assert isinstance(next(nodes), decision_tree.GetAttr)       # .to_string
    assert isinstance(next(nodes), decision_tree.CallFunction)  # ()
    assert isinstance(next(nodes), decision_tree.CallFunction)  # print(...)
    assert no_more(nodes)

    optimizer.optimize(root_node)

    nodes = iterate_passthroughnodes(root_node)
    assert isinstance(next(nodes), decision_tree.Start)
    assert isinstance(next(nodes), decision_tree.IntConstant)   # 1
    assert isinstance(next(nodes), decision_tree.IntConstant)   # 1
    assert isinstance(next(nodes), decision_tree.Plus)          # +
    assert isinstance(next(nodes), decision_tree.IntConstant)   # 1
    assert isinstance(next(nodes), decision_tree.Plus)          # +
    assert isinstance(next(nodes), decision_tree.SetVar)        # three
    assert isinstance(next(nodes), decision_tree.GetVar)        # print
    assert isinstance(next(nodes), decision_tree.GetVar)        # three
    assert isinstance(next(nodes), decision_tree.GetAttr)       # .to_string
    assert isinstance(next(nodes), decision_tree.CallFunction)  # ()
    assert isinstance(next(nodes), decision_tree.CallFunction)  # print(...)
    assert no_more(nodes)
