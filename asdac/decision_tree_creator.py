# converts cooked ast to a decision tree
# this is in separate file because decision_tree.py became >1000 lines long

import collections
import copy
import typing

from asdac import ast, decision_tree
from asdac.objects import Function, Variable


# the .type attribute of the variables doesn't contain info about
# whether the variable is wrapped in a box object or not

class _TreeCreator:

    def __init__(
            self, local_vars: typing.Dict[str, Variable]) -> None:
        self.local_vars = local_vars

        # why can't i assign in python lambda without dirty setattr haxor :(
        self.set_next_node: typing.Callable[[decision_tree.Node], None] = (
            lambda node: setattr(self, 'root_node', node))
        self.root_node: typing.Optional[decision_tree.Node] = None

    def subcreator(self) -> '_TreeCreator':
        return _TreeCreator(self.local_vars)

    def add_pass_through_node(self, node: decision_tree.Node) -> None:
        assert isinstance(node, decision_tree.PassThroughNode)
        self.set_next_node(node)
        self.set_next_node = node.set_next_node

    def do_function_call(self, call: ast.CallFunction) -> None:
        for arg in call.args:
            self.do_expression(arg)

        assert call.function is not None
        self.add_pass_through_node(decision_tree.CallFunction(
            call.function, len(call.args),
            (call.function.returntype is not None), location=call.location))

    def _do_if(
            self,
            cond: ast.Expression,
            if_callback: typing.Callable[['_TreeCreator'], None],
            else_callback: typing.Callable[['_TreeCreator'], None],
            **boilerplate: typing.Any) -> None:
        self.do_expression(cond)
        result = decision_tree.BoolDecision(**boilerplate)

        if_creator = self.subcreator()
        if_creator.set_next_node = result.set_then
        if_callback(if_creator)

        else_creator = self.subcreator()
        else_creator.set_next_node = result.set_otherwise
        else_callback(else_creator)

        def set_next_node_to_both(next_node: decision_tree.Node) -> None:
            if_creator.set_next_node(next_node)
            else_creator.set_next_node(next_node)
            return None

        self.set_next_node(result)
        self.set_next_node = set_next_node_to_both

    def do_expression(self, expression: ast.Expression) -> None:
        assert expression.type is not None
        boilerplate = {'location': expression.location}

        if isinstance(expression, ast.StrConstant):
            self.add_pass_through_node(decision_tree.StrConstant(
                expression.python_string, **boilerplate))

        elif isinstance(expression, ast.IntConstant):
            self.add_pass_through_node(decision_tree.IntConstant(
                expression.python_int, **boilerplate))

        elif isinstance(expression, ast.GetVar):
            raise NotImplementedError

        elif isinstance(expression, ast.IfExpression):
            expression2 = expression    # mypy is fucking around with me
            self._do_if(
                expression.cond,
                lambda creator: creator.do_expression(expression2.true_expr),
                lambda creator: creator.do_expression(expression2.false_expr),
                **boilerplate)

        elif isinstance(expression, ast.StrJoin):
            for part in expression.parts:
                self.do_expression(part)

            self.add_pass_through_node(decision_tree.StrJoin(
                len(expression.parts), **boilerplate))

        elif isinstance(expression, ast.CallFunction):
            self.do_function_call(expression)

        else:
            assert False, expression    # pragma: no cover

    def do_statement(self, statement: ast.Statement) -> None:
        boilerplate = {'location': statement.location}

        if isinstance(statement, ast.CallFunction):
            self.do_function_call(statement)
            if statement.type is not None:
                # not a void function, ignore return value
                self.add_pass_through_node(decision_tree.PopOne(**boilerplate))

        elif isinstance(statement, ast.IfStatement):
            statement2 = statement    # fuck you mypy
            self._do_if(
                statement.cond,
                lambda creator: creator.do_body(statement2.if_body),
                lambda creator: creator.do_body(statement2.else_body),
                **boilerplate)

        elif isinstance(statement, ast.Loop):
            creator = self.subcreator()
            if statement.pre_cond is None:
                creator.add_pass_through_node(
                    decision_tree.GetBuiltinVar('TRUE'))
            else:
                creator.do_expression(statement.pre_cond)

            beginning_decision = decision_tree.BoolDecision(**boilerplate)
            creator.set_next_node(beginning_decision)
            creator.set_next_node = beginning_decision.set_then

            creator.do_body(statement.body)
            creator.do_body(statement.incr)

            if statement.post_cond is None:
                creator.add_pass_through_node(
                    decision_tree.GetBuiltinVar('TRUE'))
            else:
                creator.do_expression(statement.post_cond)

            end_decision = decision_tree.BoolDecision(**boilerplate)
            end_decision.set_then(creator.root_node)
            creator.set_next_node(end_decision)

            def set_next_node_everywhere(node: decision_tree.Node) -> None:
                beginning_decision.set_otherwise(node)
                end_decision.set_otherwise(node)

            assert creator.root_node is not None
            self.set_next_node(creator.root_node)
            self.set_next_node = set_next_node_everywhere

        elif isinstance(statement, ast.Return):
            if statement.value is not None:
                raise NotImplementedError

            # the next node might or might not become unreachable, because
            # multiple nodes can jump to the same node
            #
            # if it becomes unreachable, tree_creation_done() cleans it up
            self.set_next_node = lambda node: None

        else:
            assert False, type(statement)     # pragma: no cover

    def do_body(self, statements: typing.List[ast.Statement]) -> None:
        for statement in statements:
            assert not isinstance(statement, list), statement
            self.do_statement(statement)


def create_tree(
    cooked_funcdefs: typing.List[ast.FuncDefinition]
) -> typing.Dict[Function, decision_tree.Start]:
    function_trees = {}
    for funcdef in cooked_funcdefs:
        creator = _TreeCreator({})

        assert funcdef.function is not None
        creator.add_pass_through_node(
            decision_tree.Start(funcdef.function.argvars.copy()))
        creator.do_body(funcdef.body)

        assert isinstance(creator.root_node, decision_tree.Start)

        # there used to be code that handled this with a less dumb algorithm
        # than clean_all_unreachable_nodes, but it didn't work in corner cases
        decision_tree.clean_all_unreachable_nodes(creator.root_node)
        function_trees[funcdef.function] = creator.root_node

        decision_tree.graphviz(creator.root_node, funcdef.function.name)

    return function_trees
