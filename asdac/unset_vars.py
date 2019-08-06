from asdac import common, decision_tree


# you can assume that the variable is set after any visited node
def _check_variable_is_set(node, getvar_node, visited_nodes):
    if isinstance(node, decision_tree.Start):
        # TODO: show variable definition location in error message
        raise common.CompileError(
            "variable '%s' might not be set" % getvar_node.var.name,
            location=getvar_node.location)

    visited_nodes.add(node)

    if isinstance(node, decision_tree.SetVar) and node.var is getvar_node.var:
        return

    if not node.jumped_from:
        # dead code
        return

    for other in node.jumped_from:
        _check_variable_is_set(other, getvar_node, visited_nodes)


def check_for_unset_variables(root_node):
    # TODO: optimize?
    for node in decision_tree.get_all_nodes(root_node):
        # builtin vars have level 0
        if isinstance(node, decision_tree.GetVar) and node.var.level > 0:
            _check_variable_is_set(node, node, set())
