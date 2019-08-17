import itertools

from asdac import decision_tree
from asdac.optimizer import decisions, variables


_function_list = [
    decisions.optimize_bool_constant_decisions,
    variables.remove_temporary_vars,
]


def optimize(root_node):
    infinite_function_iterator = itertools.cycle(_function_list)

    did_nothing_count = 0
    all_nodes = decision_tree.get_all_nodes(root_node)

    # if there are n optimizer functions, then stop when n of them have been
    # called subsequently without any of them doing anything
    while did_nothing_count < len(_function_list):
        optimizer_function = next(infinite_function_iterator)
        # TODO: don't hard-code 1
        if optimizer_function(root_node, all_nodes, 1):
            did_nothing_count = 0
            all_nodes = decision_tree.get_all_nodes(root_node)
        else:
            did_nothing_count += 1
