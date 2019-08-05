import inspect
import re

from asdac import decision_tree


def add_jumps(node_dict, instruction_string):
    # https://stackoverflow.com/a/5616910
    for start, end in re.findall(r'(?=(\w+) *-> *(\w+))', instruction_string):
        node_dict[start].add_jump_to(node_dict[end])


def test_find_merge_simple():
    a = decision_tree.Node()
    b = decision_tree.Node()
    c = decision_tree.Node()
    d = decision_tree.Node()
    e = decision_tree.Node()
    f = decision_tree.Node()

    #     a
    #    / \
    #    b  d
    #    |  |
    #    c  |
    #     \ /
    #      e
    #      |
    #      f
    add_jumps(locals(), '''
    a -> b -> c -> e -> f
    a -> d ->      e
    ''')

    assert decision_tree.find_merge(b, d) is e

    c.remove_jump_to(e)
    assert decision_tree.find_merge(b, d) is None
    c.add_jump_to(e)

    d.remove_jump_to(e)
    assert decision_tree.find_merge(b, d) is None
    d.add_jump_to(e)


def test_find_merge_cycle_and_stuff(monkeypatch):
    a = decision_tree.Node()
    b = decision_tree.Node()
    c = decision_tree.Node()
    d = decision_tree.Node()
    e = decision_tree.Node()
    f = decision_tree.Node()
    g = decision_tree.Node()
    h = decision_tree.Node()

    #      a
    #     / \
    #    b   d<--.
    #    |   |   h
    #    c   g---^
    #     \ /
    #      e
    #      |
    #      f
    add_jumps(locals(), '''
    a -> b -> c -> e -> f
    a -> d -> g -> e
              g -> h -> d
    ''')

    assert decision_tree.find_merge(b, d) is e

    b.remove_jump_to(c)
    assert decision_tree.find_merge(b, d) is None
    b.add_jump_to(c)

    # tests that it does not traverse in the wrong direction
    d.remove_jump_to(g)
    assert decision_tree.find_merge(b, d) is None
    d.add_jump_to(g)

    # tests that it handles unrelated branchings
    h.remove_jump_to(d)
    assert decision_tree.find_merge(b, d) is e
    h.add_jump_to(d)
