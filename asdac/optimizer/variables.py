from asdac import common, decision_tree


# you can assume that the variable is set after any visited node
def _find_setvars_for_getvar(node, getvar_node, visited_nodes):
    if not node.jumped_from:
        # reached e.g. decision_tree.Start node or some dead code thing
        # TODO: show variable definition location in error message
        # TODO: this should maybe be a warning instead of an error?
        #       then this should add nodes that create good error at runtime
        raise common.CompileError(
            "variable '%s' might not be set" % getvar_node.var.name,
            location=getvar_node.location)

    visited_nodes.add(node)

    if isinstance(node, decision_tree.SetVar) and node.var is getvar_node.var:
        yield node
        return

    for ref in node.jumped_from:
        if ref.objekt not in visited_nodes:
            yield from _find_setvars_for_getvar(ref.objekt, getvar_node,
                                                visited_nodes)


def _find_getvars_for_setvar(setvar_node):
    return (node for node in decision_tree.get_all_nodes(setvar_node)
            if isinstance(node, decision_tree.GetVar)
            and node.var is setvar_node.var)


def _get_setvars_and_getvars_to_dicts(all_nodes, local_var_level):
    setvar2getvars = {}
    for node in all_nodes:
        if (
          isinstance(node, decision_tree.SetVar) and
          node.var.level == local_var_level):
            setvar2getvars[node] = set(_find_getvars_for_setvar(node))

    getvar2setvars = {}
    for node in all_nodes:
        if (
          isinstance(node, decision_tree.GetVar) and
          node.var.level == local_var_level):
            assert node not in getvar2setvars
            getvar2setvars[node] = set(
                _find_setvars_for_getvar(node, node, set()))
            assert getvar2setvars[node]

    return (setvar2getvars, getvar2setvars)


# TODO: this feels like not the best way to do this?
def _optimize_set_once_get_once(setvar: decision_tree.SetVar, getvar: decision_tree.GetVar):
    # used immediately after set?
    if setvar.next_node is getvar and len(getvar.jumped_from) == 1:
        decision_tree.replace_node(setvar, getvar.next_node)
        return True

    # something that gets pushed between the set and get
    # e.g.
    #
    #   let message = "lel"
    #   print(message)
    if (
      isinstance(setvar.next_node, decision_tree.PassThroughNode) and
      # currently all nodes with .push_count==1 ignore the content of the stack
      setvar.next_node.push_count == 1 and
      setvar.next_node.next_node is getvar and
      len(setvar.next_node.jumped_from) == 1 and
      len(getvar.jumped_from) == 1):
        decision_tree.replace_node(setvar, setvar.next_node)

        swap = decision_tree.Swap2()
        swap.set_next_node(getvar.next_node)
        decision_tree.replace_node(getvar, swap)
        return True

    return False


def optimize_by_removing_temporary_vars(root_node, all_nodes, local_var_level):
    setvar2getvars, getvar2setvars = _get_setvars_and_getvars_to_dicts(
        all_nodes, local_var_level)
    did_something = False

    for setvar, getvars in setvar2getvars.items():
        if not getvars:
            # TODO: warnings should be printed MUCH more nicely
            print("warning: value of variable '%s' is set, but never used"
                  % setvar.var.name)

            # replace setvar with ignoring the value
            # TODO: mark some things as side-effect-free and implement
            #       optimizing PopOne
            ignore_value = decision_tree.PopOne()
            ignore_value.set_next_node(setvar.next_node)
            decision_tree.replace_node(setvar, ignore_value)
            did_something = True

        if len(getvars) == 1:
            [getvar] = getvars
            if len(getvar2setvars[getvar]) == 1:
                assert getvar2setvars[getvar] == {setvar}
                if _optimize_set_once_get_once(setvar, getvar):
                    did_something = True

    return did_something
