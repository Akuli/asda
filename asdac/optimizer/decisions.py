from asdac import cooked_ast, decision_tree


# handles e.g. loops and ifs with TRUE or FALSE as a condition
def optimize_bool_constant_decisions(root_node, all_nodes):
    getvars_before_decisions = {
        node for node in all_nodes
        if isinstance(node, decision_tree.GetBuiltinVar)
        and node.varname in {'TRUE', 'FALSE'}
        and isinstance(node.next_node, decision_tree.BoolDecision)
    }

    for node in getvars_before_decisions:
        if node.varname == 'TRUE':
            decision_tree.replace_node(node, node.next_node.then)
        elif node.varname == 'FALSE':
            decision_tree.replace_node(node, node.next_node.otherwise)
        else:
            raise RuntimeError("wut")

    return bool(getvars_before_decisions)
