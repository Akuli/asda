from asdac import common, decision_tree, optimizer


def _check_always_returns_a_value(node, checked, function):
    if node in checked:
        return
    checked.add(node)

    if not isinstance(node, decision_tree.StoreReturnValue):
        for subnode in node.get_jumps_to_including_nones():
            if subnode is None:
                raise common.CompileError(
                    "this function should return a value in all cases, "
                    "but seems like it doesn't",
                    function.location)
            _check_always_returns_a_value(
                subnode, checked, function)


def check_for_missing_returns(root_node, all_nodes, function):
    if function.returntype is not None:
        _check_always_returns_a_value(root_node, set(), createfunc_node)
    return False
