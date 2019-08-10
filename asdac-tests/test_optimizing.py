import pytest

from asdac import decision_tree, optimize


def iterate_passthroughnodes(node):
    while node is not None:
        if not isinstance(node, decision_tree.PassThroughNode):
            raise RuntimeError
        yield node
        node = node.next_node


def test_bool_constant_decisions(compiler):
    root_node = compiler.create_tree('''\
do:
    print("loop")
while FALSE
print("done")
''')

    with pytest.raises(RuntimeError):
        list(iterate_passthroughnodes(root_node))

    optimize.optimize(root_node)
    decision_tree.graphviz(root_node, 'test')

    nodes = iterate_passthroughnodes(root_node)
    assert isinstance(next(nodes), decision_tree.Start)

    assert isinstance(next(nodes), decision_tree.GetVar)        # print
    assert isinstance(next(nodes), decision_tree.StrConstant)   # "loop"
    assert isinstance(next(nodes), decision_tree.CallFunction)

    assert isinstance(next(nodes), decision_tree.GetVar)        # print
    assert isinstance(next(nodes), decision_tree.StrConstant)   # "done"
    assert isinstance(next(nodes), decision_tree.CallFunction)

    with pytest.raises(StopIteration):
        next(nodes)
