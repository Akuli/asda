# converts cooked ast to a decision tree
# this is in separate file because decision_tree.py became >1000 lines long

import copy

from asdac import cooked_ast, decision_tree, objects


class _TreeCreator:

    def __init__(self, local_vars_level, local_vars_list, exit_points,
                 unreachable_nodes_to_clean_up):
        # from now on, local variables are items in the beginning of the stack
        #
        # also the .type attribute of the variables doesn't contain info about
        # whether the variable is wrapped in a box object or not
        self.local_vars_level = local_vars_level
        self.local_vars_list = local_vars_list

        # closures are implemented with automagically partialling the variables
        # as function arguments
        #
        # the automagically created argument variables have a different level
        # than the variables being partialled, so they need different variable
        # objects
        #
        # this dict contains those
        # keys are variables with .level < self.local_vars_level
        # values are argument variables with .level == self.local_vars_level
        self.closure_vars = {}

        # .set_next_node methods that should be called to make stuff run every
        # time the function is about to early-return
        # used for cleaning up local variables from stack
        # not used in non-function tree creators
        self.exit_points = exit_points

        # unreachable nodes are generally bad, so keep list of them and clean
        # them up before passing to next compile step
        self.unreachable_nodes_to_clean_up = unreachable_nodes_to_clean_up

        # why can't i assign in python lambda without dirty setattr haxor :(
        self.set_next_node = lambda node: setattr(self, 'root_node', node)
        self.root_node = None

    def subcreator(self):
        return _TreeCreator(
            self.local_vars_level, self.local_vars_list, self.exit_points,
            self.unreachable_nodes_to_clean_up)

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

    def _add_to_varlist(self, local_var, *, append=True):
        assert local_var.level == self.local_vars_level
        if local_var not in self.local_vars_list:
            if append:
                self.local_vars_list.append(local_var)
            else:
                self.local_vars_list.insert(0, local_var)

    def get_local_closure_var(self, nonlocal_var):
        try:
            return self.closure_vars[nonlocal_var]
        except KeyError:
            local = copy.copy(nonlocal_var)
            local.level = self.local_vars_level
            self.closure_vars[nonlocal_var] = local
            return local

    # returns whether unboxing is needed
    def _add_var_lookup_without_unboxing(self, var, **boilerplate) -> bool:
        if var.level == 0:
            self.add_pass_through_node(
                decision_tree.GetBuiltinVar(var.name, **boilerplate))
            return False

        if var.level == self.local_vars_level:
            self._add_to_varlist(var)
            # None is fixed later
            node = decision_tree.GetFromBottom(None, var, **boilerplate)
        else:
            # closure variable
            local = self.get_local_closure_var(var)
            self._add_to_varlist(local, append=False)
            node = decision_tree.GetFromBottom(None, local, **boilerplate)

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

        elif isinstance(expression, decision_tree.IntConstant):
            self.add_pass_through_node(decision_tree.IntConstant(
                expression.python_int, **boilerplate))

        elif isinstance(expression, cooked_ast.GetVar):
            var = expression.var    # pep8 line length
            if self._add_var_lookup_without_unboxing(var, **boilerplate):
                self.add_pass_through_node(decision_tree.UnBox())

        elif isinstance(expression, cooked_ast.IfExpression):
            self._do_if(
                expression.cond,
                lambda creator: creator.do_expression(expression.true_expr),
                lambda creator: creator.do_expression(expression.false_expr),
                **boilerplate)

        elif isinstance(expression, decision_tree.PrefixMinus):
            self.do_expression(expression.prefixed)
            self.add_pass_through_node(
                decision_tree.PrefixMinus(**boilerplate))

        elif isinstance(expression, (
                decision_tree.Plus, decision_tree.Minus,
                decision_tree.Times,
                cooked_ast.Equal, cooked_ast.NotEqual)):
            self.do_expression(expression.lhs)
            self.do_expression(expression.rhs)

            if isinstance(expression, decision_tree.Plus):
                self.add_pass_through_node(decision_tree.Plus(**boilerplate))
            elif isinstance(expression, decision_tree.Times):
                self.add_pass_through_node(decision_tree.Times(**boilerplate))
            elif isinstance(expression, decision_tree.Minus):
                self.add_pass_through_node(decision_tree.Minus(**boilerplate))
            else:
                # push TRUE or FALSE to stack, usually this gets optimized into
                # something that doesn't involve bool objects at all
                eq = decision_tree.EqualDecision(**boilerplate)

                if isinstance(expression, cooked_ast.Equal):
                    eq.set_then(decision_tree.GetBuiltinVar('TRUE'))
                    eq.set_otherwise(decision_tree.GetBuiltinVar('FALSE'))
                elif isinstance(expression, cooked_ast.NotEqual):
                    eq.set_then(decision_tree.GetBuiltinVar('FALSE'))
                    eq.set_otherwise(decision_tree.GetBuiltinVar('TRUE'))
                else:
                    raise RuntimeError("wuut")      # pragma: no cover

                self.set_next_node(eq)
                self.set_next_node = lambda node: (
                    eq.then.set_next_node(node),
                    eq.otherwise.set_next_node(node),
                )

        elif isinstance(expression, decision_tree.StrJoin):
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
        elif isinstance(expression, decision_tree.CreateFunction):
            creator = _TreeCreator(self.local_vars_level + 1,
                                   expression.argvars.copy(), [],
                                   self.unreachable_nodes_to_clean_up)
            creator.add_pass_through_node(decision_tree.Start(
                expression.argvars.copy()))
            creator.do_body(expression.body)
            creator.fix_variable_stuff()

            partialling = creator.get_nonlocal_vars_to_partial()
            for var in partialling:
                needs_unbox = self._add_var_lookup_without_unboxing(var)
                assert needs_unbox

            tybe = objects.FunctionType(
                [var.type for var in partialling] + expression.type.argtypes,
                expression.type.returntype)

            self.add_pass_through_node(decision_tree.CreateFunction(
                tybe, creator.root_node, **boilerplate))

            if partialling:
                self.add_pass_through_node(
                    decision_tree.CreatePartialFunction(len(partialling)))

        else:
            assert False, expression    # pragma: no cover

    def do_statement(self, statement):
        boilerplate = {'location': statement.location}

        if isinstance(statement, cooked_ast.CreateLocalVar):
            pass

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

        elif isinstance(statement, decision_tree.SetAttr):
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
            self.exit_points.append(self.set_next_node)
            self.set_next_node = self.unreachable_nodes_to_clean_up.append

        elif isinstance(statement, decision_tree.Throw):
            self.do_expression(statement.value)
            self.add_pass_through_node(decision_tree.Throw(**boilerplate))

        elif isinstance(statement, decision_tree.SetMethodsToClass):
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

    def fix_variable_stuff(self):
        assert isinstance(self.root_node, decision_tree.Start)

        for node in decision_tree.get_all_nodes(self.root_node):
            if isinstance(node, (decision_tree.SetToBottom,
                                 decision_tree.GetFromBottom)):
                node.index = self.local_vars_list.index(node.var)

        closure_argvars = self.local_vars_list[:len(self.closure_vars)]
        creator = self.subcreator()
        creator.add_pass_through_node(decision_tree.Start(
            closure_argvars + self.root_node.argvars))
        assert isinstance(creator.root_node, decision_tree.Start)

        for var in self.local_vars_list[len(creator.root_node.argvars):]:
            creator.add_pass_through_node(decision_tree.CreateBox(var))

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
        for index, var in enumerate(self.root_node.argvars,
                                    start=len(self.closure_vars)):
            add = creator.add_pass_through_node     # pep8 line length
            add(decision_tree.GetFromBottom(index, var))
            add(decision_tree.CreateBox(var))
            add(decision_tree.SetToBottom(index, var))
            add(decision_tree.GetFromBottom(index, var))
            add(decision_tree.SetToBox())

        if self.root_node.next_node is not None:
            creator.set_next_node(self.root_node.next_node)
            creator.set_next_node = self.set_next_node

        for index, var in enumerate(self.local_vars_list):
            pop = decision_tree.PopOne(is_popping_a_dummy=True)
            if index == 0:      # first time
                for func in creator.exit_points:
                    func(pop)
                creator.exit_points.clear()
            creator.add_pass_through_node(pop)

        # avoid creating an unreachable node
        self.root_node.set_next_node(None)

        self.root_node = creator.root_node
        self.set_next_node = creator.set_next_node

    def get_nonlocal_vars_to_partial(self):
        local2nonlocal = {
            local: nonl0cal for nonl0cal, local in self.closure_vars.items()}
        return [local2nonlocal[local]
                for local in self.local_vars_list[:len(self.closure_vars)]]


def create_tree(cooked_statements):
    tree_creator = _TreeCreator(1, [], [], [])
    tree_creator.add_pass_through_node(decision_tree.Start([]))

    tree_creator.do_body(cooked_statements)
    tree_creator.fix_variable_stuff()
    assert not tree_creator.get_nonlocal_vars_to_partial()

    for node in tree_creator.unreachable_nodes_to_clean_up:
        decision_tree.clean_unreachable_nodes_given_one_of_them(node)

    assert isinstance(tree_creator.root_node, decision_tree.Start)
    return tree_creator.root_node
