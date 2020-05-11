import itertools
import typing

from asdac import decision_tree, objects
from asdac.optimizer import copy_pasta, decisions, functions, popone


_optimizer_lists: typing.List[typing.List[typing.Callable[
    [
        decision_tree.Start,                # root node
        typing.Set[decision_tree.Node],    # all nodes
        objects.Function,                # which function we are optimizing
    ],
    bool,   # did it actually do something?
]]] = [
    # start by optimizing gently so that other things e.g. understand that
    # a loop like 'while TRUE' never ends
    [decisions.optimize_truefalse_before_booldecision],

    # Check all the things. These functions always return False, because they
    # don't actually optimize anything by changing the nodes etc
    [#variables.check_boxes_set,
     functions.check_for_missing_returns],

    # now we can actually optimize
    # In the future, these steps could be skipped for e.g. debugging
    #
    # TODO: commented out ones
    [copy_pasta.optimize_similar_nodes,
     decisions.optimize_booldecision_before_truefalse,
     #variables.optimize_temporary_vars,
     #variables.optimize_unnecessary_boxes,
     #variables.optimize_variable_assigned_to_itself,
     popone.optimize_popones,
     ],
]


# there used to be lots of jumped_from bugs, if there are any then this errors
def _check_jumped_froms(all_nodes: typing.Set[decision_tree.Node]) -> None:
    for node in all_nodes:
        for ref in node.jumped_from:
            assert ref.objekt in all_nodes


def optimize(function_trees: typing.Dict[
        objects.Function, decision_tree.Start]) -> None:

    # optimize each function
    for function, root_node in function_trees.items():
        for optimizer_list in _optimizer_lists:
            infinite_optimizer_iterator = itertools.cycle(optimizer_list)
            did_nothing_count = 0
            all_nodes = decision_tree.get_all_nodes(root_node)
            _check_jumped_froms(all_nodes)

            # if there are n optimizer functions, then stop when n of them have
            # been called subsequently without any of them doing anything
            while did_nothing_count < len(optimizer_list):
                optimizer_function = next(infinite_optimizer_iterator)
                if optimizer_function(root_node, all_nodes, function):
                    did_nothing_count = 0
                    all_nodes = decision_tree.get_all_nodes(root_node)
                    try:
                        _check_jumped_froms(all_nodes)
                    except AssertionError:
                        #decision_tree.graphviz(root_node, 'error')
                        raise
                else:
                    did_nothing_count += 1

    # TODO: remove unused functions and generate warnings for them
