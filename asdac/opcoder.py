import bisect
import collections
import io
import itertools

from . import decision_tree, common, cooked_ast, objects


class VarMarker(common.Marker):
    pass


class ArgMarker:

    def __init__(self, index):
        self.index = index

    def __repr__(self):
        return '%s(%d)' % (type(self).__name__, self.index)


# lineno is None for ops that don't correspond to a cooked ast node
def _op_class(name, fields):
    return collections.namedtuple(name, ['lineno'] + fields)


# all types are cooked_ast types
StrConstant = _op_class('StrConstant', ['python_string'])
IntConstant = _op_class('IntConstant', ['python_int'])
BoolConstant = _op_class('BoolConstant', ['python_bool'])
CreateFunction = _op_class('CreateFunction', ['functype', 'body_opcode'])
# tuples have an index() method, avoid name clash with misspelling
GetFromModule = _op_class('GetFromModule', ['compilation', 'indeks'])
SetVar = _op_class('SetVar', ['level', 'var'])
GetVar = _op_class('GetVar', ['level', 'var'])
SetAttr = _op_class('SetAttr', ['type', 'indeks'])
GetAttr = _op_class('GetAttr', ['type', 'indeks'])
CallFunction = _op_class('CallFunction', ['nargs'])
CallConstructor = _op_class('CallConstructor', ['tybe', 'nargs'])
StrJoin = _op_class('StrJoin', ['how_many_parts'])
PopOne = _op_class('PopOne', [])
Return = _op_class('Return', ['returns_a_value'])
Throw = _op_class('Throw', [])
BoolNegation = _op_class('BoolNegation', [])
Jump = _op_class('Jump', ['marker'])
JumpIf = _op_class('JumpIf', ['marker'])
DidntReturnError = _op_class('DidntReturnError', [])
SetMethodsToClass = _op_class('SetMethodsToClass', ['klass',
                                                    'how_many_methods'])

Plus = _op_class('Plus', [])
Minus = _op_class('Minus', [])
PrefixMinus = _op_class('PrefixMinus', [])
Times = _op_class('Times', [])
# Divide = _op_class('Divide', [])
Equal = _op_class('Equal', [])

# items are tuples: (jumpto_marker, errortype, errorvarlevel, errorvar)
AddErrorHandler = _op_class('AddErrorHandler', ['items'])
RemoveErrorHandler = _op_class('RemoveErrorHandler', [])

PushFinallyStateOk = _op_class('PushFinallyStateOk', [])
PushFinallyStateError = _op_class('PushFinallyStateError', [])
PushFinallyStateReturn = _op_class('PushFinallyStateReturn', [
    'returns_a_value'])
PushFinallyStateJump = _op_class('PushFinallyStateJump', ['index'])
DiscardFinallyState = _op_class('DiscardFinallyState', [])
ApplyFinallyState = _op_class('ApplyFinallyState', [])


# convenience thing to add an error handler with just 1 item
def _add_simple_error_handler(lineno, jumpto_marker, errortype,
                              errorvarlevel, errorvar):
    item = (jumpto_marker, errortype, errorvarlevel, errorvar)
    return AddErrorHandler(lineno, [item])


class JumpMarker(common.Marker):

    def __init__(self):
        super().__init__()
        self.lineno = None


# debugging tip: pprint.pprint(opcode.ops)
class OpCode:

    def __init__(self, nargs, max_stack_size):
        self.nargs = nargs
        self.ops = []
        self.local_vars = [ArgMarker(i) for i in range(nargs)]
        self.max_stack_size = max_stack_size

    def add_local_var(self):
        var = VarMarker()
        self.local_vars.append(var)
        return var

    def _get_all_ops(self):
        # i wish python had pointer objects or something :(
        # sucks to yield (list, index) pairs
        # in c, i could use &self.ops[index]
        for index, op in enumerate(self.ops):
            yield (self.ops, index)
            if isinstance(op, CreateFunction):
                yield from op.body_opcode._get_all_ops()

    def fix_none_linenos(self):
        current_lineno = 1
        for lizt, index in self._get_all_ops():
            if lizt[index].lineno is None:
                if isinstance(lizt[index], JumpMarker):
                    lizt[index].lineno = current_lineno
                else:
                    # _replace is a documented namedtuple method, it has _ to
                    # allow creating a namedtuple with a 'replace' attribute
                    lizt[index] = lizt[index]._replace(lineno=current_lineno)
            else:
                current_lineno = lizt[index].lineno


class _OpCoder:

    def __init__(self, output_opcode, compilation):
        self.output = output_opcode
        self.parent_coder = None
        self.level = 0
        self.compilation = compilation

        # keys are cooked_ast.Variable or cooked_ast.GenericVariable
        # values are VarMarker or ArgMarker
        self.local_vars = {}

        self.node2jumpmarker = {}

    def create_subcoder(self, output_opcode):
        result = _OpCoder(output_opcode, self.compilation)
        result.parent_coder = self
        result.level = self.level + 1
        return result

    def _get_coder_for_level(self, level):
        level_difference = self.level - level
        assert level_difference >= 0

        coder = self
        for lel in range(level_difference):
            coder = coder.parent_coder
        return coder

    def opcode_passthroughnode(self, node):
        if len(node.jumped_from) > 1:
            marker = JumpMarker()
            self.node2jumpmarker[node] = marker
            self.output.ops.append(marker)

        if isinstance(node, (decision_tree.SetVar, decision_tree.GetVar)):
            coder = self._get_coder_for_level(node.var.level)
            if node.var not in coder.local_vars:
                coder.local_vars[node.var] = coder.output.add_local_var()

            if isinstance(node, decision_tree.SetVar):
                self.output.ops.append(SetVar(
                    node.lineno, node.var.level, coder.local_vars[node.var]))
            else:
                self.output.ops.append(GetVar(
                    node.lineno, node.var.level, coder.local_vars[node.var]))

        elif isinstance(node, decision_tree.StrConstant):
            self.output.ops.append(StrConstant(
                node.lineno, node.python_string))

        elif isinstance(node, decision_tree.IntConstant):
            self.output.ops.append(IntConstant(node.lineno, node.python_int))

        elif isinstance(node, decision_tree.Equal):
            self.output.ops.append(Equal(node.lineno))

        elif isinstance(node, decision_tree.CallFunction):
            self.output.ops.append(CallFunction(
                node.lineno, node.how_many_args))

        else:
            print(dir(node))
            raise NotImplementedError(repr(node))

    def opcode_tree(self, node):
        # FIXME: handle loops
        while node is not None:
            if isinstance(node, decision_tree.PassThroughNode):
                self.opcode_passthroughnode(node)
                node = node.next_node

            elif isinstance(node, decision_tree.BoolDecision):
                # FIXME: duplicates all opcode after the if,else
                then_marker = JumpMarker()
                done_marker = JumpMarker()

                self.output.ops.append(JumpIf(node.lineno, then_marker))
                self.opcode_tree(node.otherwise)
                self.output.ops.append(Jump(None, done_marker))
                self.output.ops.append(then_marker)
                self.opcode_tree(node.then)
                self.output.ops.append(done_marker)
                node = None

            else:
                raise NotImplementedError(repr(node))


def create_opcode(compilation, root_node, export_vars):
    builtin_opcoder = _OpCoder(None, compilation)
    builtin_opcoder.local_vars.update({
        var: ArgMarker(index)
        for index, var in enumerate(itertools.chain(
            cooked_ast.BUILTIN_VARS.values(),
            cooked_ast.BUILTIN_GENERIC_VARS.values(),
        ))
    })

    # exported symbols are kinda like arguments
    output = OpCode(len(export_vars),
                    decision_tree.get_max_stack_size(root_node))
    file_opcoder = builtin_opcoder.create_subcoder(output)
    for arg_marker, var in zip(output.local_vars, export_vars.values()):
        file_opcoder.local_vars[var] = arg_marker

    file_opcoder.opcode_tree(root_node)
    import pprint; pprint.pprint(output.ops)
    output.fix_none_linenos()
    return output
