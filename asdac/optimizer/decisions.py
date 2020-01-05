from asdac import decision_tree


# handles e.g. loops and ifs with TRUE or FALSE as a condition
def optimize_truefalse_before_booldecision(root_node, all_nodes,
                                           createfunc_node):
    for node in all_nodes:
        if (
          isinstance(node, decision_tree.GetBuiltinVar) and
          isinstance(node.next_node, decision_tree.BoolDecision)):
            if node.varname == 'TRUE':
                decision_tree.replace_node(node, node.next_node.then)
                return True
            if node.varname == 'FALSE':
                decision_tree.replace_node(node, node.next_node.otherwise)
                return True

    return False


def optimize_booldecision_before_truefalse(
        root_node, all_nodes, createfunc_node):
    for node in all_nodes:
        if (
          isinstance(node, decision_tree.BoolDecision) and
          isinstance(node.then, decision_tree.GetBuiltinVar) and
          isinstance(node.otherwise, decision_tree.GetBuiltinVar) and
          node.then.varname == 'TRUE' and
          node.otherwise.varname == 'FALSE' and
          node.then.next_node is node.otherwise.next_node):
            decision_tree.replace_node(node, node.then.next_node)
            return True
    return False
