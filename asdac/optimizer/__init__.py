import itertools

from asdac import decision_tree
from asdac.optimizer import copy_pasta, decisions, functions, variables


_function_lists = [
    # do functions first, because an entire CreateFunction node can get
    # optimized away if the function is never used, but is good to get error
    # messages and warnings from inside function definitions like that anyway
    [functions.optimize_function_bodies],

    # start by optimizing gently so that other things e.g. understand that
    # a loop like 'while TRUE' never ends
    [decisions.optimize_truefalse_before_booldecision],

    # Check all the things. These functions always return False, because they
    # don't actually optimize anything by changing the nodes etc
    [variables.check_variables_set,
     functions.check_for_missing_returns],

    # now we can actually optimize
    # In the future, these steps could be skipped for e.g. debugging
    [copy_pasta.optimize_similar_nodes,
     decisions.optimize_booldecision_before_truefalse,
     variables.optimize_temporary_vars,
     variables.optimize_garbage_dummies],
]


# there used to be lots of jumped_from bugs, if there are any then this errors
def _check_jumped_froms(all_nodes):
    for node in all_nodes:
        for ref in node.jumped_from:
            assert ref.objekt in all_nodes


def optimize(root_node, createfunc_node):
    did_something = False

    for function_list in _function_lists:
        infinite_function_iterator = itertools.cycle(function_list)
        did_nothing_count = 0
        all_nodes = decision_tree.get_all_nodes(root_node)
        _check_jumped_froms(all_nodes)

        # if there are n optimizer functions, then stop when n of them have
        # been called subsequently without any of them doing anything
        while did_nothing_count < len(function_list):
            optimizer_function = next(infinite_function_iterator)
            if optimizer_function(root_node, all_nodes, createfunc_node):
                did_something = True
                did_nothing_count = 0
                all_nodes = decision_tree.get_all_nodes(root_node)
                try:
                    _check_jumped_froms(all_nodes)
                except AssertionError:
                    #decision_tree.graphviz(root_node, 'error')
                    raise
            else:
                did_nothing_count += 1

    return did_something
