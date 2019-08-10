from asdac import cooked_ast, decision_tree


# handles e.g. loops and ifs with TRUE or FALSE as a condition
def _optimize_bool_constant_decisions(root_node):
    interesting_nodes = {
        node for node in decision_tree.get_all_nodes(root_node)
        if isinstance(node, decision_tree.GetVar)
        and node.var in {cooked_ast.BUILTIN_VARS['TRUE'],
                         cooked_ast.BUILTIN_VARS['FALSE']}
        and isinstance(node.next_node, decision_tree.BoolDecision)
    }

    for node in interesting_nodes:
        if node.var is cooked_ast.BUILTIN_VARS['TRUE']:
            decision_tree.replace_node(node, node.next_node.then)
        elif node.var is cooked_ast.BUILTIN_VARS['FALSE']:
            decision_tree.replace_node(node, node.next_node.otherwise)
        else:
            raise RuntimeError("wut")

    return bool(interesting_nodes)


_optimizers = [_optimize_bool_constant_decisions]


def optimize(root_node):
    # i wish python had do,while :(
    did_something = True
    while did_something:
        did_something = False
        for func in _optimizers:
            if func(root_node):
                did_something = True
