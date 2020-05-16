# converts cooked ast to a decision tree
# this is in separate file because dtree.py became >1000 lines long

import functools
import typing

from asdac import ast
from asdac import decision_tree as dtree
from asdac.common import Location
from asdac.objects import Function, Variable, VariableKind


# the .type attribute of the variables doesn't contain info about
# whether the variable is wrapped in a box object or not


class _TreeCreator:

    def __init__(self, local_vars: typing.Dict[Variable, dtree.ObjectId]):
        self.local_vars = local_vars

        # why can't i assign in python lambda without dirty setattr haxor :(
        self.set_next_node: typing.Callable[[dtree.Node], None] = (
            lambda node: setattr(self, 'root_node', node))
        self.root_node: typing.Optional[dtree.Node] = None

    def subcreator(self) -> '_TreeCreator':
        return _TreeCreator(self.local_vars)

    def do_expression(self, expression: ast.Expression) -> dtree.ObjectId:
        assert expression.type is not None

        result_id = dtree.ObjectId()

        if isinstance(expression, ast.StrConstant):
            self.add_pass_through_node(dtree.StrConstant(
                expression.location, expression.python_string, result_id))

        elif isinstance(expression, ast.IntConstant):
            self.add_pass_through_node(dtree.IntConstant(
                expression.location, expression.python_int, result_id))

        elif isinstance(expression, ast.GetVar):
            assert expression.var is not None
            if expression.var.kind == VariableKind.BUILTIN:
                self.add_pass_through_node(dtree.GetBuiltinVar(
                    expression.location, expression.var, result_id))
            else:
                assert expression.var.kind == VariableKind.LOCAL
                result_id = self.local_vars[expression.var]

        elif isinstance(expression, ast.IfExpression):
            def callback(
                    true_or_false_expr: ast.Expression,
                    creator: _TreeCreator) -> None:
                temp_id = creator.do_expression(true_or_false_expr)
                creator.add_pass_through_node(dtree.Assign(
                    true_or_false_expr.location, temp_id, result_id))

            self._do_if(
                expression.location,
                expression.cond,
                functools.partial(callback, expression.true_expr),
                functools.partial(callback, expression.false_expr))

        elif isinstance(expression, ast.StrJoin):
            ids = list(map(self.do_expression, expression.parts))
            self.add_pass_through_node(dtree.StrJoin(
                expression.location, ids, result_id))

        elif isinstance(expression, ast.CallFunction):
            # weird variable name stuff needed because mypy
            temp_result_id = self.do_function_call(expression)
            assert temp_result_id is not None
            result_id = temp_result_id

        else:
            assert False, expression    # pragma: no cover

        return result_id

    def add_pass_through_node(
            self, node: dtree.PassThroughNode) -> None:
        self.set_next_node(node)
        self.set_next_node = node.set_next_node

    def do_function_call(
            self, call: ast.CallFunction) -> typing.Optional[dtree.ObjectId]:
        assert call.function is not None
        id_list = [self.do_expression(arg) for arg in call.args]
        if call.function.returntype is None:
            result_id = None
        else:
            result_id = dtree.ObjectId()

        self.add_pass_through_node(dtree.CallFunction(
            call.location, call.function, id_list,
            result_id))
        return result_id

    def _do_if(
        self,
        location: Location,
        cond: ast.Expression,
        if_callback: typing.Callable[['_TreeCreator'], None],
        else_callback: typing.Callable[['_TreeCreator'], None],
    ) -> None:
        cond_id = self.do_expression(cond)
        result = dtree.BoolDecision(location, cond_id)

        if_creator = self.subcreator()
        if_creator.set_next_node = result.set_then
        if_callback(if_creator)

        else_creator = self.subcreator()
        else_creator.set_next_node = result.set_otherwise
        else_callback(else_creator)

        def set_next_node_to_both(next_node: dtree.Node) -> None:
            if_creator.set_next_node(next_node)
            else_creator.set_next_node(next_node)
            return None

        self.set_next_node(result)
        self.set_next_node = set_next_node_to_both

    def do_statement(self, statement: ast.Statement) -> None:
        if isinstance(statement, ast.CallFunction):
            self.do_function_call(statement)

        elif isinstance(statement, ast.IfStatement):
            statement2 = statement    # fuck you mypy
            self._do_if(
                statement.location,
                statement.cond,
                lambda creator: creator.do_body(statement2.if_body),
                lambda creator: creator.do_body(statement2.else_body))

        elif isinstance(statement, ast.Loop):
            creator = self.subcreator()
            if statement.pre_cond is None:
                creator.add_pass_through_node(
                    dtree.GetBuiltinVar('TRUE'))
            else:
                creator.do_expression(statement.pre_cond)

            beginning_decision = dtree.BoolDecision(statement.location)
            creator.set_next_node(beginning_decision)
            creator.set_next_node = beginning_decision.set_then

            creator.do_body(statement.body)
            creator.do_body(statement.incr)

            if statement.post_cond is None:
                creator.add_pass_through_node(
                    dtree.GetBuiltinVar('TRUE'))
            else:
                creator.do_expression(statement.post_cond)

            end_decision = dtree.BoolDecision(statement.location)
            end_decision.set_then(creator.root_node)
            creator.set_next_node(end_decision)

            def set_next_node_everywhere(node: dtree.Node) -> None:
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

        elif isinstance(statement, ast.Throw):
            self.set_next_node(dtree.Throw(statement.location))

            # the next node might or might not become unreachable, because
            # multiple nodes can jump to the same node
            #
            # if it becomes unreachable, tree_creation_done() cleans it up
            self.set_next_node = lambda node: None

        elif isinstance(statement, ast.Let):
            assert statement.var is not None
            assert statement.var not in self.local_vars
            self.local_vars[statement.var] = self.do_expression(
                statement.initial_value)

        elif isinstance(statement, ast.SetVar):
            assert statement.var is not None
            assert statement.var in self.local_vars
            self.local_vars[statement.var] = self.do_expression(
                statement.value)

        else:
            assert False, type(statement)     # pragma: no cover

    def do_start(
            self, location: Location, argvars: typing.List[Variable]) -> None:
        object_ids = [dtree.ObjectId(var) for var in argvars]
        self.local_vars.update(zip(argvars, object_ids))
        self.add_pass_through_node(dtree.Start(location, object_ids))

    def do_body(self, statements: typing.List[ast.Statement]) -> None:
        for statement in statements:
            assert not isinstance(statement, list), statement
            self.do_statement(statement)


def create_tree(
    cooked_funcdefs: typing.List[ast.FuncDefinition]
) -> typing.Dict[Function, dtree.Start]:
    function_trees = {}
    for funcdef in cooked_funcdefs:
        creator = _TreeCreator({})

        assert funcdef.function is not None
        creator.do_start(funcdef.location, funcdef.function.argvars)
        creator.do_body(funcdef.body)

        assert isinstance(creator.root_node, dtree.Start)

        # there used to be code that handled this with a less dumb algorithm
        # than clean_all_unreachable_nodes, but it didn't work in corner cases
        dtree.clean_all_unreachable_nodes(creator.root_node)
        function_trees[funcdef.function] = creator.root_node

        dtree.graphviz(creator.root_node, funcdef.function.name)

    return function_trees
