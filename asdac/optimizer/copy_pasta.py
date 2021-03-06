# if nodes c and d are "similar", this optimizes e.g. this...
#
#   ... ...
#    |   |
#    a   b
#    |   |
#    c   d
#     \ /
#      e
#
# ...to this:
#
#   ... ...
#    |   |
#    a   b
#     \ /
#      c
#      |
#      e
#
# currently this doesn't work without an 'e' node, but i think that's actually
# good, because then the "optimization" would add jumps to the opcode

import itertools

from asdac import decision_tree


def _nodes_are_similar(a: decision_tree.Node, b: decision_tree.Node):
    def they_are(klass):
        return isinstance(a, klass) and isinstance(b, klass)

    if they_are(decision_tree.GetBuiltinVar):
        return a.varname == b.varname
    if (
      they_are(decision_tree.SetLocalVar) or
      they_are(decision_tree.GetLocalVar)):
        return a.var == b.var
    if they_are(decision_tree.PopOne):
        return a.is_popping_a_dummy == b.is_popping_a_dummy
    if (
      they_are(decision_tree.Plus) or
      they_are(decision_tree.Times) or
      they_are(decision_tree.StoreReturnValue) or
      they_are(decision_tree.CreateBox) or
      they_are(decision_tree.SetToBox) or
      they_are(decision_tree.UnBox)):
        return True
    if they_are(decision_tree.GetAttr):
        return a.tybe is b.tybe and a.attrname is b.attrname
    if they_are(decision_tree.StrConstant):
        return a.python_string == b.python_string
    if they_are(decision_tree.IntConstant):
        return a.python_int == b.python_int
    if they_are(decision_tree.CallFunction):
        return (a.how_many_args == b.how_many_args and
                a.is_returning == b.is_returning)
    if they_are(decision_tree.StrJoin):
        return a.how_many_strings == b.how_many_strings
    return False


def optimize_similar_nodes(start_node, all_nodes, createfunc_node):
    for node in all_nodes:
        jumped_from = (
            ref.objekt for ref in node.jumped_from
            if isinstance(ref.objekt, decision_tree.PassThroughNode)
        )

        for a, b in itertools.combinations(jumped_from, 2):
            assert a.next_node is node
            assert b.next_node is node

            if _nodes_are_similar(a, b):
                decision_tree.replace_node(a, b)
                # TODO: is it safe to optimize more than one a,b pair at once?
                return True

    return False
