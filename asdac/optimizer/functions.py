from asdac import decision_tree, optimizer


def optimize_function_bodies(root_node, all_nodes):
    did_something = False
    for node in all_nodes:
        if isinstance(node, decision_tree.CreateFunction):
            if optimizer.optimize(node.body_root_node):
                did_something = True

    return did_something
