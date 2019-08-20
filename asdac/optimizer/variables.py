from asdac import common, decision_tree


def _find_gets_for_set(set_node):
    return (node for node in decision_tree.get_all_nodes(set_node)
            if isinstance(node, decision_tree.GetFromBottom)
            and node.var is set_node.var)


# you can assume that the variable is set after any visited node
def _find_sets_for_get(node, get_node, visited_nodes, start_node):
    is_initial_argument_value = (
        node is start_node and get_node.var in start_node.argvars)

    if (not node.jumped_from) and (not is_initial_argument_value):
        # FIXME: does this handle unreachable nodes correctly?
        # TODO: show variable definition location in error message
        # TODO: mention this error in spec
        raise common.CompileError(
            "variable '%s' might not be set" % get_node.var.name,
            location=get_node.location)

    visited_nodes.add(node)

    if (
      isinstance(node, decision_tree.SetToBottom) and
      node.var is get_node.var):
        yield node
        return

    for ref in node.jumped_from:
        if ref.objekt not in visited_nodes:
            yield from _find_sets_for_get(
                ref.objekt, get_node, visited_nodes, start_node)


def _sets_and_gets_to_dicts(all_nodes, start_node):
    set2gets = {}
    for node in all_nodes:
        if isinstance(node, decision_tree.SetToBottom):
            assert node not in set2gets
            set2gets[node] = set(_find_gets_for_set(node))

    get2sets = {}
    for node in all_nodes:
        if isinstance(node, decision_tree.GetFromBottom):
            assert node not in get2sets
            get2sets[node] = set(_find_sets_for_get(
                node, node, set(), start_node))
            # get2sets[node] may be empty for function arguments

    return (set2gets, get2sets)


def _optimize_set_once_get_once(set_node, get_node):
    if set_node.next_node is get_node and len(get_node.jumped_from) == 1:
        # used immediately after set
        assert [ref.objekt for ref in get_node.jumped_from] == [set_node]
        decision_tree.replace_node(set_node, get_node.next_node)
        return True

    # TODO: some way to optimize the case where other stuff gets pushes between
    # I used to have code that would handle a common case with a thing that
    # swapped top 2 elements on the stack, but it didn't feel right

    return False


def optimize_temporary_vars(root_node, all_nodes):
    assert isinstance(root_node, decision_tree.Start)
    set2gets, get2sets = _sets_and_gets_to_dicts(all_nodes, root_node)
    did_something = False

    for set_node, gets in set2gets.items():
        if not gets:
            # TODO: warnings should be printed MUCH more nicely
            print("warning: value of variable '%s' is set, but never used"
                  % set_node.var.name)

            # replace setvar with ignoring the value
            # TODO: mark some things as side-effect-free and implement
            #       optimizing PopOne
            ignore_value = decision_tree.PopOne()
            ignore_value.set_next_node(set_node.next_node)
            decision_tree.replace_node(set_node, ignore_value)
            did_something = True

        if len(gets) == 1 and set_node.var not in root_node.argvars:
            [get_node] = gets
            if len(get2sets[get_node]) == 1:
                assert get2sets[get_node] == {set_node}
                if _optimize_set_once_get_once(set_node, get_node):
                    did_something = True

    return did_something


def _set_to_list(lizt, index, value):
    while len(lizt) <= index:
        lizt.append(None)
    lizt[index] = value


# lol = list of lists
def _append_to_inner_list(lol, lol_index, value):
    while len(lol) <= lol_index:
        lol.append([])
    lol[lol_index].append(value)


# optimize_away_temporary_vars() leaves unnecessary dummies around
def optimize_garbage_dummies(root_node, all_nodes):
    assert isinstance(root_node, decision_tree.Start)

    # pushes contains PushDummy nodes, or None for arguments
    pushes = [None] * len(root_node.argvars)
    pops = []       # PopOne nodes
    uses = []       # lists of SetToBottom or GetFromBottom

    stack_sizes = decision_tree.get_stack_sizes(root_node)

    for node in all_nodes:
        if isinstance(node, decision_tree.PushDummy):
            _set_to_list(pushes, stack_sizes[node], node)
        elif (isinstance(node, decision_tree.PopOne) and
              node.is_popping_a_dummy):
            assert node.size_delta == -1
            _set_to_list(pops, stack_sizes[node] + node.size_delta, node)
        elif isinstance(node, (decision_tree.SetToBottom,
                               decision_tree.GetFromBottom)):
            _append_to_inner_list(uses, node.index, node)

    assert len(pushes) == len(pops)

    # needed because all dummies have PushDummy and PopOne but some might have
    # no uses
    while len(uses) < len(pushes):
        uses.append([])
    assert len(uses) == len(pops)

    assert all(push is None for push in pushes[:len(root_node.argvars)])
    assert None not in pushes[len(root_node.argvars):]
    assert None not in pops
    assert None not in uses

    if all(uses[len(root_node.argvars):]):
        return False

    # looping with an index because deleting items screws up indexes
    i = len(root_node.argvars)
    while i < len(uses):
        if uses[i]:
            i += 1
            continue

        decision_tree.replace_node(pushes[i], pushes[i].next_node)
        decision_tree.replace_node(pops[i], pops[i].next_node)
        del pushes[i]
        del pops[i]
        del uses[i]

        for use_list in uses[i:]:
            for use in use_list:
                use.index -= 1
                assert use.index >= 0

    assert all(uses[len(root_node.argvars):])
    return True
