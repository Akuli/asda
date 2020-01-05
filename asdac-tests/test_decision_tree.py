import inspect
import re

from asdac import decision_tree


# 'TestBlah' is special naming for pytest
class NodeForTesting(decision_tree.Node):

    def __init__(self):
        super().__init__()
        self.jumps_to = []

    def get_jumps_to(self):
        return self.jumps_to

    def __repr__(self):
        try:
            return self.name
        except AttributeError:
            return super().__repr__()


def setup_nodes(node_dict, instruction_string):
    for name, node in node_dict.items():
        if isinstance(node, NodeForTesting):
            node.name = name

    # https://stackoverflow.com/a/5616910
    for start, end in re.findall(r'(?=(\w+) *-> *(\w+))', instruction_string):
        node_dict[start].jumps_to.append(node_dict[end])


def test_algorithms_simple():
    a = NodeForTesting()
    b = NodeForTesting()
    c = NodeForTesting()
    d = NodeForTesting()
    e = NodeForTesting()
    f = NodeForTesting()

    #     a
    #    / \
    #    b  d
    #    |  |
    #    c  |
    #     \ /
    #      e
    #      |
    #      f
    setup_nodes(locals(), '''
    a -> b -> c -> e -> f
    a -> d ->      e
    ''')

    assert decision_tree.get_all_nodes(a) == {a, b, c, d, e, f}
    assert decision_tree.find_merge([b, d]) is e

    c.remove_jump_to(e)
    assert decision_tree.get_all_nodes(a) == {a, b, c, d, e, f}
    assert decision_tree.find_merge([b, d]) is None
    c.add_jump_to(e)

    d.remove_jump_to(e)
    assert decision_tree.get_all_nodes(a) == {a, b, c, d, e, f}
    assert decision_tree.find_merge([b, d]) is None
    d.add_jump_to(e)


def test_algorithms_cycle_and_stuff(monkeypatch):
    a = NodeForTesting()
    b = NodeForTesting()
    c = NodeForTesting()
    d = NodeForTesting()
    e = NodeForTesting()
    f = NodeForTesting()
    g = NodeForTesting()
    h = NodeForTesting()

    #      a
    #     / \
    #    b   d<--.
    #    |   |   h
    #    c   g---^
    #     \ /
    #      e
    #      |
    #      f
    setup_nodes(locals(), '''
    a -> b -> c -> e -> f
    a -> d -> g -> e
              g -> h -> d
    ''')

    assert decision_tree.get_all_nodes(a) == {a, b, c, d, e, f, g, h}
    assert decision_tree.find_merge([b, d]) is e

    b.remove_jump_to(c)
    assert decision_tree.get_all_nodes(a) == {a, b, d, e, f, g, h}
    assert decision_tree.find_merge([b, d]) is None
    b.add_jump_to(c)

    # tests that it does not traverse in the wrong direction
    d.remove_jump_to(g)
    assert decision_tree.get_all_nodes(a) == {a, b, c, d, e, f}
    assert decision_tree.find_merge([b, d]) is None
    d.add_jump_to(g)

    # tests that it handles unrelated branchings
    h.remove_jump_to(d)
    assert decision_tree.get_all_nodes(a) == {a, b, c, d, e, f, g, h}
    assert decision_tree.find_merge([b, d]) is e
    h.add_jump_to(d)


def test_find_merge_special_cases():
    a = NodeForTesting()
    b = NodeForTesting()
    c = NodeForTesting()
    d = NodeForTesting()
    e = NodeForTesting()
    setup_nodes(locals(), '''
    a -> e
    b -> e
    c -> d -> e
    e -> e
    ''')

    assert decision_tree.find_merge([a, b, c]) is e
    assert decision_tree.find_merge([a]) is a
    assert decision_tree.find_merge([e]) is a
    assert decision_tree.find_merge([]) is None
