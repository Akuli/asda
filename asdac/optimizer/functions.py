from asdac import common, decision_tree, optimizer


def _check_always_returns_a_value(node, checked, createfunc_node):
    if node in checked:
        return
    checked.add(node)

    if not isinstance(node, decision_tree.StoreReturnValue):
        for subnode in node.get_jumps_to_including_nones():
            if subnode is None:
                raise common.CompileError(
                    "this function should return a value in all cases, "
                    "but seems like it doesn't",
                    createfunc_node.location)
            _check_always_returns_a_value(
                subnode, checked, createfunc_node)


def check_for_missing_returns(root_node, all_nodes, createfunc_node):
    if (
      createfunc_node is not None and
      createfunc_node.functype.returntype is not None):
        _check_always_returns_a_value(root_node, set(), createfunc_node)

    return False


def optimize_function_bodies(root_node, all_nodes, createfunc_node):
    did_something = False
    for node in all_nodes:
        if isinstance(node, decision_tree.CreateFunction):
            if optimizer.optimize(node.body_root_node, node):
                did_something = True

    return did_something
