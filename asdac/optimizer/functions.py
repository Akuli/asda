import typing

from asdac import common, cooked_ast, decision_tree, optimizer


# FIXME: functions that return a value must always do that, check it here
def check_for_missing_returns(
        root_node: decision_tree.Start,
        all_nodes: typing.Set[decision_tree.Node],
        function: cooked_ast.Function) -> bool:
    return False
