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


def check_boxes_set(start_node, all_nodes, createfunc_node):
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


def _remove_box_if_possible(create_box, start_node):
    assert isinstance(create_box.next_node, decision_tree.SetLocalVar)
    box_var = create_box.next_node.var

    sets = set()
    gets = set()

    for node in decision_tree.get_all_nodes(create_box.next_node.next_node):
        # if this assert fails, you need to add code to handle setting a box
        # variable
        assert not (isinstance(node, decision_tree.SetLocalVar) and
                    node.var is box_var)

        if not (isinstance(node, decision_tree.GetLocalVar) and
                node.var is box_var):
            continue

        if isinstance(node.next_node, decision_tree.SetToBox):
            sets.add(node)
        elif isinstance(node.next_node, decision_tree.UnBox):
            gets.add(node)
        else:
            # don't know what is being done with this box, maybe it is actually
            # needed because it's being passed to something that sets stuff
            # to it
            #
            # TODO: handle the case where the box goes to a function as a
            # closure variable, but the function never sets it
            return False

    for node in sets:
        # replace GetLocalVar and SetToBox with SetLocalVar
        new_node = decision_tree.SetLocalVar(node.var, location=node.location)
        new_node.set_next_node(node.next_node.next_node)
        decision_tree.replace_node(node, new_node)

    for node in gets:
        # remove UnBox
        decision_tree.replace_node(node.next_node, node.next_node.next_node)

    decision_tree.replace_node(create_box, create_box.next_node.next_node)
    return True


def optimize_unnecessary_boxes(start_node, all_nodes, createfunc_node):
    for create_box in all_nodes:
        if isinstance(create_box, decision_tree.CreateBox):
            if _remove_box_if_possible(create_box, start_node):
                return True
    return False


def _find_gets_for_set(node: decision_tree.Node, var, visited_nodes):
    visited_nodes.add(node)

    if isinstance(node, decision_tree.GetLocalVar) and node.var is var:
        yield node
    if isinstance(node, decision_tree.SetLocalVar) and node.var is var:
        return

    for other_node in node.get_jumps_to():
        if other_node not in visited_nodes:
            yield from _find_gets_for_set(other_node, var, visited_nodes)


def _find_sets_for_var(node, var, visited_nodes):
    visited_nodes.add(node)

    if isinstance(node, decision_tree.SetLocalVar) and node.var is var:
        yield node
        return

    for ref in node.jumped_from:
        if ref.objekt not in visited_nodes:
            yield from _find_sets_for_var(ref.objekt, var, visited_nodes)


def _sets_and_gets_to_dicts(all_nodes, start_node):
    set2gets = {}
    for node in all_nodes:
        if isinstance(node, decision_tree.SetLocalVar):
            assert node not in set2gets
            if node.next_node is None:
                set2gets[node] = set()
            else:
                set2gets[node] = set(_find_gets_for_set(
                    node.next_node, node.var, set()))

    get2sets = {}
    for node in all_nodes:
        if isinstance(node, decision_tree.GetLocalVar):
            assert node not in get2sets
            get2sets[node] = set(_find_sets_for_var(node, node.var, set()))
            # get2sets[node] may be empty for function arguments

    return (set2gets, get2sets)


def _optimize_set_once_get_once(set_node, get_node):
    if set_node.next_node is get_node:
        # used immediately after set
        assert set_node in (ref.objekt for ref in get_node.jumped_from)
        decision_tree.replace_node(set_node, get_node.next_node)
        return True

    # TODO: some way to optimize the case where other stuff gets pushes between
    # I used to have code that would handle a common case with a thing that
    # swapped top 2 elements on the stack, but it didn't feel right

    return False


def optimize_temporary_vars(root_node, all_nodes, createfunc_node):
    assert isinstance(root_node, decision_tree.Start)
    set2gets, get2sets = _sets_and_gets_to_dicts(all_nodes, root_node)

    for set_node, gets in set2gets.items():
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

        if len(gets) == 1 and set_node.var not in root_node.argvars:
            [get_node] = gets
            if len(get2sets[get_node]) == 1:
                assert get2sets[get_node] == {set_node}
                if _optimize_set_once_get_once(set_node, get_node):
                    return True

    return False


def optimize_variable_assigned_to_itself(
        root_node, all_nodes, createfunc_node):
    for node in all_nodes:
        if (
          isinstance(node, decision_tree.GetLocalVar) and
          isinstance(node.next_node, decision_tree.SetLocalVar) and
          node.var is node.next_node.var):
            decision_tree.replace_node(node, node.next_node.next_node)
            return True

    return False
