import typing

from asdac import common, decision_tree, optimizer, objects


# FIXME: functions that return a value must always do that, check it here
def check_for_missing_returns(
        start_node: decision_tree.Start,
        all_nodes: typing.Set[decision_tree.Node],
        function: objects.Function) -> bool:
    return False
