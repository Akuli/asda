# optimizes away unnecessary nodes

import typing

from asdac import cooked_ast, decision_tree


# TODO:
#    CreateFunction
#    CreatePartialFunction
#    StrJoin
#    everything that is currently commented out
def _skip_unnecessary_nodes(node: decision_tree.Node) -> bool:
    if not (isinstance(node, decision_tree.PassThroughNode) and
            isinstance(node.next_node, decision_tree.PopOne)):
        return False

#    if isinstance(node, (decision_tree.UnBox, decision_tree.GetAttr)):
#        # e.g. pop the box instead of an unboxed value
#        # will likely get optimized more when this function is called again
#        decision_tree.replace_node(node, node.next_node)
#        return True

    if isinstance(node, (
                decision_tree.GetBuiltinVar,
#                decision_tree.GetLocalVar,
#                decision_tree.CreateBox,
                decision_tree.StrConstant,
                decision_tree.IntConstant,
#                decision_tree.CreateFunction,
            )):
        assert node.use_count == 0
        assert node.size_delta == 1

        decision_tree.replace_node(node, node.next_node.next_node)
        return True

    if isinstance(node, (decision_tree.Plus, decision_tree.Times)):
        assert node.use_count == 2
        assert node.size_delta == -1

        # pop the two things being added or multiplied
        # need to add another PopOne for that
        # again, this may get optimized more when called again
        new_pop = decision_tree.PopOne()
        new_pop.set_next_node(node.next_node)
        decision_tree.replace_node(node, new_pop)
        return True

    return False


def optimize_popones(
        start_node: decision_tree.Start,
        all_nodes: typing.Set[decision_tree.Node],
        function: cooked_ast.Function) -> bool:
    for node in all_nodes:
        if _skip_unnecessary_nodes(node):
            # all_nodes is no longer an up to date list of nodes, need to stop
            return True
    return False
