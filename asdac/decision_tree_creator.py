# converts cooked ast to a decision tree
# this is in separate file because decision_tree.py became >1000 lines long

import collections
import copy

from asdac import cooked_ast, decision_tree, objects


class _TreeCreator:

    def __init__(self, level, local_vars, closure_vars):
        # the .type attribute of the variables doesn't contain info about
        # whether the variable is wrapped in a box object or not
        self.level = level
        self.local_vars = local_vars

        # closures are implemented with automagically partialling the variables
        # as function arguments
        #
        # the automagically created argument variables have a different level
        # than the variables being partialled, so they need different variable
        # objects
        #
        # this dict contains those
        # keys are variables with .level < self.level
        # values are argument variables with .level == self.level
        #
        # doesn't really need to be ordered, just needs to be consistent
        assert isinstance(closure_vars, collections.OrderedDict)
        self.closure_vars = closure_vars

        # why can't i assign in python lambda without dirty setattr haxor :(
        self.set_next_node = lambda node: setattr(self, 'root_node', node)
        self.root_node = None

    def subcreator(self):
        return _TreeCreator(self.level, self.local_vars, self.closure_vars)

    def add_pass_through_node(self, node):
        assert isinstance(node, decision_tree.PassThroughNode)
        self.set_next_node(node)
        self.set_next_node = node.set_next_node

    def do_function_call(self, call):
        self.do_expression(call.function)
        for arg in call.args:
            self.do_expression(arg)

        self.add_pass_through_node(decision_tree.CallFunction(
            len(call.args), (call.function.type.returntype is not None),
            location=call.location))

    def get_local_closure_var(self, nonlocal_var):
        try:
            return self.closure_vars[nonlocal_var]
        except KeyError:
            local = copy.copy(nonlocal_var)
            local.level = self.level
            self.closure_vars[nonlocal_var] = local
            return local

    # returns whether unboxing is needed
    def _add_var_lookup_without_unboxing(self, var, **boilerplate) -> bool:
        if var.level == 0:
            self.add_pass_through_node(
                decision_tree.GetBuiltinVar(var.name, **boilerplate))
            return False

        if var.level == self.level:
            self.local_vars.add(var)
            node = decision_tree.GetLocalVar(var, **boilerplate)
        else:
            # closure variable
            local = self.get_local_closure_var(var)
            self.local_vars.add(local)
            node = decision_tree.GetLocalVar(local, **boilerplate)

        self.add_pass_through_node(node)
        return True

    def _do_if(self, cond, if_callback, else_callback, **boilerplate):
        self.do_expression(cond)
        result = decision_tree.BoolDecision(**boilerplate)

        if_creator = self.subcreator()
        if_creator.set_next_node = result.set_then
        if_callback(if_creator)

        else_creator = self.subcreator()
        else_creator.set_next_node = result.set_otherwise
        else_callback(else_creator)

        self.set_next_node(result)
        self.set_next_node = lambda next_node: (
            if_creator.set_next_node(next_node),
            else_creator.set_next_node(next_node),
        )

    def do_expression(self, expression):
        assert expression.type is not None
        boilerplate = {'location': expression.location}

        if isinstance(expression, cooked_ast.StrConstant):
            self.add_pass_through_node(decision_tree.StrConstant(
                expression.python_string, **boilerplate))

        elif isinstance(expression, cooked_ast.IntConstant):
            self.add_pass_through_node(decision_tree.IntConstant(
                expression.python_int, **boilerplate))

        elif isinstance(expression, cooked_ast.GetVar):
            var = expression.var    # pep8 line length
            if self._add_var_lookup_without_unboxing(var, **boilerplate):
                self.add_pass_through_node(decision_tree.UnBox())

        elif isinstance(expression, cooked_ast.GetFromModule):
            self.add_pass_through_node(decision_tree.GetFromModule(
                expression.other_compilation, expression.name, **boilerplate))

        elif isinstance(expression, cooked_ast.IfExpression):
            self._do_if(
                expression.cond,
                lambda creator: creator.do_expression(expression.true_expr),
                lambda creator: creator.do_expression(expression.false_expr),
                **boilerplate)

        elif isinstance(expression, cooked_ast.BoolNegation):
            self.do_expression(expression.value)

            # this is dumb, but usually gets optimized a lot
            decision = decision_tree.BoolDecision(**boilerplate)
            decision.set_then(decision_tree.GetBuiltinVar('FALSE'))
            decision.set_otherwise(decision_tree.GetBuiltinVar('TRUE'))

            self.set_next_node(decision)
            self.set_next_node = lambda node: (
                decision.then.set_next_node(node),
                decision.otherwise.set_next_node(node),
            )

        elif isinstance(expression, cooked_ast.PrefixMinus):
            self.do_expression(expression.prefixed)
            self.add_pass_through_node(
                decision_tree.PrefixMinus(**boilerplate))

        elif isinstance(expression, (
                cooked_ast.Plus, cooked_ast.Minus, cooked_ast.Times,
                cooked_ast.StrEqual, cooked_ast.IntEqual)):
            self.do_expression(expression.lhs)
            self.do_expression(expression.rhs)

            if isinstance(expression, cooked_ast.Plus):
                self.add_pass_through_node(decision_tree.Plus(**boilerplate))
            elif isinstance(expression, cooked_ast.Times):
                self.add_pass_through_node(decision_tree.Times(**boilerplate))
            elif isinstance(expression, cooked_ast.Minus):
                self.add_pass_through_node(decision_tree.Minus(**boilerplate))
            else:
                # push TRUE or FALSE to stack, usually this gets optimized into
                # something that doesn't involve bool objects at all
                if isinstance(expression, cooked_ast.IntEqual):
                    eq = decision_tree.IntEqualDecision(**boilerplate)
                else:
                    eq = decision_tree.StrEqualDecision(**boilerplate)
                eq.set_then(decision_tree.GetBuiltinVar('TRUE'))
                eq.set_otherwise(decision_tree.GetBuiltinVar('FALSE'))

                self.set_next_node(eq)
                self.set_next_node = lambda node: (
                    eq.then.set_next_node(node),
                    eq.otherwise.set_next_node(node),
                )

        elif isinstance(expression, cooked_ast.StrJoin):
            for part in expression.parts:
                self.do_expression(part)

            self.add_pass_through_node(decision_tree.StrJoin(
                len(expression.parts), **boilerplate))

        elif isinstance(expression, cooked_ast.CallFunction):
            self.do_function_call(expression)

        elif isinstance(expression, cooked_ast.New):
            for arg in expression.args:
                self.do_expression(arg)

            self.add_pass_through_node(decision_tree.CallConstructor(
                expression.type, len(expression.args), **boilerplate))

        elif isinstance(expression, cooked_ast.GetAttr):
            self.do_expression(expression.obj)
            self.add_pass_through_node(decision_tree.GetAttr(
                expression.obj.type, expression.attrname, **boilerplate))

        # TODO: when closures work again, figure out how to do closures
        #       for arguments of the function
        elif isinstance(expression, cooked_ast.CreateFunction):
            creator = _TreeCreator(
                self.level + 1,
                set(expression.argvars),
                collections.OrderedDict())

            creator.add_pass_through_node(decision_tree.Start(
                expression.argvars.copy()))
            creator.do_body(expression.body)
            creator.tree_creation_done()

            partialling = creator.closure_vars.keys()
            for var in partialling:
                needs_unbox = self._add_var_lookup_without_unboxing(var)
                assert needs_unbox

            tybe = objects.FunctionType(
                [var.type for var in partialling] + expression.type.argtypes,
                expression.type.returntype)

            local_argvars = (
                list(creator.closure_vars.values()) + expression.argvars)
            self.add_pass_through_node(decision_tree.CreateFunction(
                tybe, creator.root_node, local_argvars, **boilerplate))

            if partialling:
                self.add_pass_through_node(
                    decision_tree.CreatePartialFunction(len(partialling)))

        else:
            assert False, expression    # pragma: no cover

    def do_statement(self, statement):
        boilerplate = {'location': statement.location}

        if isinstance(statement, cooked_ast.CreateLocalVar):
            # currently not used, but may be useful in the future
            pass

        elif isinstance(statement, cooked_ast.ExportObject):
            self.do_expression(statement.value)
            self.add_pass_through_node(
                decision_tree.ExportObject(statement.name, **boilerplate))

        elif isinstance(statement, cooked_ast.CallFunction):
            self.do_function_call(statement)
            if statement.type is not None:
                # not a void function, ignore return value
                self.add_pass_through_node(decision_tree.PopOne(**boilerplate))

        elif isinstance(statement, cooked_ast.SetVar):
            self.do_expression(statement.value)
            its_a_box = self._add_var_lookup_without_unboxing(
                statement.var, **boilerplate)
            assert its_a_box
            self.add_pass_through_node(decision_tree.SetToBox())

        elif isinstance(statement, cooked_ast.SetAttr):
            self.do_expression(statement.value)
            self.do_expression(statement.obj)
            self.add_pass_through_node(decision_tree.SetAttr(
                statement.obj.type, statement.attrname))

        elif isinstance(statement, cooked_ast.IfStatement):
            self._do_if(
                statement.cond,
                lambda creator: creator.do_body(statement.if_body),
                lambda creator: creator.do_body(statement.else_body),
                **boilerplate)

        elif isinstance(statement, cooked_ast.Loop):
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

            self.set_next_node(creator.root_node)
            self.set_next_node = lambda node: (
                beginning_decision.set_otherwise(node),
                end_decision.set_otherwise(node),
            )

        elif isinstance(statement, cooked_ast.Return):
            if statement.value is not None:
                self.do_expression(statement.value)
                self.add_pass_through_node(
                    decision_tree.StoreReturnValue(**boilerplate))

            # the next node might or might not become unreachable, because
            # multiple nodes can jump to the same node
            #
            # if it becomes unreachable, tree_creation_done() cleans it up
            self.set_next_node = lambda node: None

        elif isinstance(statement, cooked_ast.Throw):
            self.do_expression(statement.value)
            self.add_pass_through_node(decision_tree.Throw(**boilerplate))

        elif isinstance(statement, cooked_ast.SetMethodsToClass):
            for method in statement.methods:
                self.do_expression(method)
            self.add_pass_through_node(decision_tree.SetMethodsToClass(
                statement.klass, len(statement.methods)))

        else:
            assert False, type(statement)     # pragma: no cover

    def do_body(self, statements):
        for statement in statements:
            assert not isinstance(statement, list), statement
            self.do_statement(statement)

    def tree_creation_done(self):
        assert isinstance(self.root_node, decision_tree.Start)

        closure_argvars = list(self.closure_vars.values())
        creator = self.subcreator()
        creator.add_pass_through_node(decision_tree.Start(
            closure_argvars + self.root_node.argvars))
        assert isinstance(creator.root_node, decision_tree.Start)

        for var in self.local_vars - set(creator.root_node.argvars):
            creator.add_pass_through_node(decision_tree.CreateBox())
            creator.add_pass_through_node(decision_tree.SetLocalVar(var))

        # wrap arguments into new boxes
        # usually will be optimized away, but is not always with nested
        # functions, e.g.
        #
        #   let create_counter = (Int i) -> functype{() -> void}:
        #       return () -> void:
        #           i = i+1
        #           print(i.to_string())
        #
        # this will create a box of i, which is needed in the inner function
        #
        # TODO: put the boxes to different variable and fix the types
        #       currently there is no type for a box, so "box of T" variables
        #       have type T
        for var in self.root_node.argvars:
            creator.add_pass_through_node(decision_tree.GetLocalVar(var))
            creator.add_pass_through_node(decision_tree.CreateBox())
            creator.add_pass_through_node(decision_tree.SetLocalVar(var))
            creator.add_pass_through_node(decision_tree.GetLocalVar(var))
            creator.add_pass_through_node(decision_tree.SetToBox())

        if self.root_node.next_node is not None:
            creator.set_next_node(self.root_node.next_node)
            creator.set_next_node = self.set_next_node

        # avoid creating an unreachable node
        self.root_node.set_next_node(None)

        self.root_node = creator.root_node
        self.set_next_node = creator.set_next_node

        # there used to be code that handled this with a less dumb algorithm
        # than decision_tree.clean_all_unreachable_nodes, but it didn't work in
        # all corner cases
        decision_tree.clean_all_unreachable_nodes(self.root_node)


def create_tree(cooked_statements):
    tree_creator = _TreeCreator(1, set(), collections.OrderedDict())
    tree_creator.add_pass_through_node(decision_tree.Start([]))

    tree_creator.do_body(cooked_statements)
    tree_creator.tree_creation_done()
    assert not tree_creator.closure_vars

    assert isinstance(tree_creator.root_node, decision_tree.Start)
    return tree_creator.root_node
