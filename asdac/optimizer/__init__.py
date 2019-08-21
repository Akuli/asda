import itertools

from asdac import decision_tree
from asdac.optimizer import (
    copy_pasta, decisions, functions, unreachable_nodes, variables)


_function_lists = [
    # do functions first, because an entire CreateFunction node can get
    # optimized away if the function is never used, but is good to get error
    # messages and warnings from inside function definitions like that anyway
    [functions.optimize_function_bodies],

    # start by optimizing gently so that other things e.g. understand that
    # a loop like 'while TRUE' never ends
    [decisions.optimize_truefalse_before_booldecision],

    # TODO: this haxor shouldn't be needed
    # this code doesn't compile without haxor:
    #
    #    if TRUE:
    #        outer let x = 123
    #    print("{x}")
    #
    [unreachable_nodes.optimize_unreachable_nodes],

    # Check all the things. These functions always return False, because they
    # don't actually optimize anything by changing the nodes etc
    [variables.check_variables_set,
     functions.check_for_missing_returns],

    # now we can actually optimize
    # In the future, these steps could be skipped for e.g. debugging
    [copy_pasta.optimize_similar_nodes,
     decisions.optimize_booldecision_before_truefalse,
     variables.optimize_temporary_vars,
     variables.optimize_garbage_dummies,
     unreachable_nodes.optimize_unreachable_nodes],
]


def optimize(root_node, createfunc_node):
    did_something = False

    for function_list in _function_lists:
        infinite_function_iterator = itertools.cycle(function_list)
        did_nothing_count = 0
        all_nodes = decision_tree.get_all_nodes(root_node)

        # if there are n optimizer functions, then stop when n of them have
        # been called subsequently without any of them doing anything
        while did_nothing_count < len(function_list):
            optimizer_function = next(infinite_function_iterator)
            if optimizer_function(root_node, all_nodes, createfunc_node):
                did_something = True
                did_nothing_count = 0
                all_nodes = decision_tree.get_all_nodes(root_node)
            else:
                did_nothing_count += 1

    return did_something
