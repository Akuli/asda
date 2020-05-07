from asdac import common, decision_tree


# you can assume that the variable is set after any visited node
def _check_matching_sets_exist(node, var, error_location, visited_nodes):
    if not node.jumped_from:
        assert isinstance(node, decision_tree.Start)
        if var in node.argvars:
            return

        # TODO: variable definition location in error message
        # TODO: mention this error in spec
        raise common.CompileError(
            "variable '%s' might not be set" % var.name, error_location)

    visited_nodes.add(node)

    if (
      isinstance(node, decision_tree.GetLocalVar) and
      node.var is var and
      isinstance(node.next_node, decision_tree.SetToBox)):
        return

    for ref in node.jumped_from:
        if ref.objekt not in visited_nodes:
            _check_matching_sets_exist(
                ref.objekt, var, error_location, visited_nodes)


def check_boxes_set(start_node, all_nodes, function):
    for node in all_nodes:
        if not isinstance(node, decision_tree.UnBox):
            continue

        for ref in node.jumped_from:
            assert isinstance(ref.objekt, decision_tree.GetLocalVar)
            _check_matching_sets_exist(
                ref.objekt, ref.objekt.var, ref.objekt.location, set())


def nexts(node, n):
    for i in range(n):
        node = node.next_node
    return node


def optimize_unnecessary_boxes(start_node, all_nodes, function):
    for create_box in all_nodes:
        if isinstance(create_box, decision_tree.CreateBox):
            if _remove_box_if_possible(create_box, start_node):
                return True
    return False


def optimize_temporary_vars(root_node, all_nodes, function):
    assert isinstance(root_node, decision_tree.Start)

    # 'blah in argvars' runs slightly but measurably faster than list lookups
    argvars = set(root_node.argvars)

    for set_node, gets in _find_sets_and_their_gets(all_nodes):
        if not gets:
            # TODO: warnings should be printed MUCH more nicely
            print("warning: value of variable '%s' is set, but never used"
                  % set_node.var.name)

            # replace SetToBottom with ignoring the value
            # PopOne is likely to get optimized away
            ignore_value = decision_tree.PopOne()
            ignore_value.set_next_node(set_node.next_node)
            decision_tree.replace_node(set_node, ignore_value)
            return True

        if len(gets) == 1 and set_node.var not in argvars:
            [get_node] = gets
            set_nodes = set(_find_sets_for_var(get_node, get_node.var, set()))

            if len(set_nodes) == 1:
                assert set_nodes == {set_node}
                if _optimize_set_once_get_once(set_node, get_node):
                    return True

    return False
