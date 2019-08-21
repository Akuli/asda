from asdac import cooked_ast, decision_tree


# handles e.g. loops and ifs with TRUE or FALSE as a condition
def optimize_truefalse_before_booldecision(root_node, all_nodes,
                                           createfunc_node):
    truefalses_before_decisions = {
        node for node in all_nodes
        if isinstance(node, decision_tree.GetBuiltinVar)
        and node.varname in {'TRUE', 'FALSE'}
        and isinstance(node.next_node, decision_tree.BoolDecision)
    }

    for node in truefalses_before_decisions:
        if node.varname == 'TRUE':
            decision_tree.replace_node(node, node.next_node.then)
        elif node.varname == 'FALSE':
            decision_tree.replace_node(node, node.next_node.otherwise)
        else:
            raise RuntimeError("wut")       # pragma: no cover

    return bool(truefalses_before_decisions)


def optimize_booldecision_before_truefalse(
        root_node, all_nodes, createfunc_node):
    useless_decisions = {
        node for node in all_nodes
        if isinstance(node, decision_tree.BoolDecision)
        and isinstance(node.then, decision_tree.GetBuiltinVar)
        and isinstance(node.otherwise, decision_tree.GetBuiltinVar)
        and node.then.varname == 'TRUE'
        and node.otherwise.varname == 'FALSE'
        and node.then.next_node is node.otherwise.next_node
    }

    for decision in useless_decisions:
        decision_tree.replace_node(decision, decision.then.next_node)

    return bool(useless_decisions)
