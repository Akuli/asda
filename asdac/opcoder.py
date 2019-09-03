import bisect
import collections
import io
import itertools

from . import decision_tree, common, cooked_ast


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
PushDummy = _op_class('PushDummy', [])
CreateFunction = _op_class('CreateFunction', ['functype', 'body_opcode'])
CreatePartialFunction = _op_class('CreatePartialFunction', ['how_many_args'])
# tuples have an index() method, avoid name clash with misspelling
GetFromModule = _op_class('GetFromModule', ['compilation', 'indeks'])
GetBuiltinVar = _op_class('GetBuiltinVar', ['varname'])
SetToBottom = _op_class('SetToBottom', ['indeks'])
GetFromBottom = _op_class('GetFromBottom', ['indeks'])
CreateBox = _op_class('CreateBox', [])
SetToBox = _op_class('SetToBox', [])
UnBox = _op_class('UnBox', [])
SetAttr = _op_class('SetAttr', ['type', 'indeks'])
GetAttr = _op_class('GetAttr', ['type', 'indeks'])
CallFunction = _op_class('CallFunction', ['nargs'])
CallConstructor = _op_class('CallConstructor', ['tybe', 'nargs'])
StrJoin = _op_class('StrJoin', ['how_many_parts'])
PopOne = _op_class('PopOne', [])
StoreReturnValue = _op_class('StoreReturnValue', [])
Throw = _op_class('Throw', [])
Jump = _op_class('Jump', ['marker'])
JumpIf = _op_class('JumpIf', ['marker'])
JumpIfEqual = _op_class('JumpIfEqual', ['marker'])
SetMethodsToClass = _op_class('SetMethodsToClass', ['klass',
                                                    'how_many_methods'])

Plus = _op_class('Plus', [])
Minus = _op_class('Minus', [])
PrefixMinus = _op_class('PrefixMinus', [])
Times = _op_class('Times', [])
# Divide = _op_class('Divide', [])

# items are tuples: (jumpto_marker, errortype, errorvarlevel, errorvar)
AddErrorHandler = _op_class('AddErrorHandler', ['items'])
RemoveErrorHandler = _op_class('RemoveErrorHandler', [])

PushFinallyStateOk = _op_class('PushFinallyStateOk', [])
PushFinallyStateError = _op_class('PushFinallyStateError', [])
PushFinallyStateReturn = _op_class('PushFinallyStateReturn', [])
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

    def __init__(self, max_stack_size):
        self.ops = []
        self.max_stack_size = max_stack_size

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

    def __init__(self, output_opcode, compilation, line_start_offsets):
        self.output = output_opcode
        self.compilation = compilation
        self.line_start_offsets = line_start_offsets

        # keys are opcoded nodes, values are JumpMarker objects
        #
        # this is a simple way to handle loops, code common to both branches of
        # a decision, etc
        self.jump_cache = {}

    # returns line number so that 1 means first line
    def _lineno(self, location):
        if location is None:
            return None

        #    >>> offsets = [0, 4, 10]
        #    >>> bisect.bisect(offsets, 0)
        #    1
        #    >>> bisect.bisect(offsets, 3)
        #    1
        #    >>> bisect.bisect(offsets, 4)
        #    2
        #    >>> bisect.bisect(offsets, 8)
        #    2
        #    >>> bisect.bisect(offsets, 9)
        #    2
        #    >>> bisect.bisect(offsets, 10)
        #    3
        assert location.compilation == self.compilation
        return bisect.bisect(self.line_start_offsets, location.offset)

    def attrib_index(self, tybe, name):
        assert isinstance(tybe.attributes, collections.OrderedDict)
        return list(tybe.attributes.keys()).index(name)

    def opcode_passthroughnode(self, node):
        lineno = self._lineno(node.location)

        if isinstance(node, decision_tree.Start):
            return

        simple = [
            (decision_tree.Plus, Plus),
            (decision_tree.Times, Times),
            (decision_tree.PrefixMinus, PrefixMinus),
            (decision_tree.PushDummy, PushDummy),
            (decision_tree.PopOne, PopOne),
            (decision_tree.StoreReturnValue, StoreReturnValue),
        ]
        for node_class, op_class in simple:
            if isinstance(node, node_class):
                self.output.ops.append(op_class(lineno))
                return

        if isinstance(node, decision_tree.GetBuiltinVar):
            self.output.ops.append(GetBuiltinVar(lineno, node.varname))
            return

        if isinstance(node, decision_tree.SetToBottom):
            self.output.ops.append(SetToBottom(lineno, node.index))
            return

        if isinstance(node, decision_tree.GetFromBottom):
            self.output.ops.append(GetFromBottom(lineno, node.index))
            return

        if isinstance(node, decision_tree.CreateBox):
            self.output.ops.append(CreateBox(lineno))
            return

        if isinstance(node, decision_tree.SetToBox):
            self.output.ops.append(SetToBox(lineno))
            return

        if isinstance(node, decision_tree.UnBox):
            self.output.ops.append(UnBox(lineno))
            return

        if isinstance(node, decision_tree.GetAttr):
            self.output.ops.append(GetAttr(
                lineno, node.tybe,
                self.attrib_index(node.tybe, node.attrname)))
            return

        if isinstance(node, decision_tree.StrConstant):
            self.output.ops.append(StrConstant(lineno, node.python_string))
            return

        if isinstance(node, decision_tree.IntConstant):
            self.output.ops.append(IntConstant(lineno, node.python_int))
            return

        if isinstance(node, decision_tree.CallFunction):
            self.output.ops.append(CallFunction(
                lineno, node.how_many_args))
            return

        if isinstance(node, decision_tree.CallConstructor):
            self.output.ops.append(CallConstructor(
                lineno, node.tybe, node.how_many_args))
            return

        if isinstance(node, decision_tree.StrJoin):
            self.output.ops.append(StrJoin(
                lineno, node.how_many_strings))
            return

        if isinstance(node, decision_tree.CreateFunction):
            function_opcode = OpCode(
                decision_tree.get_max_stack_size(node.body_root_node))
            opcoder = _OpCoder(
                function_opcode, self.compilation, self.line_start_offsets)
            opcoder.opcode_tree(node.body_root_node)
            self.output.ops.append(CreateFunction(
                lineno, node.functype, function_opcode))
            return

        if isinstance(node, decision_tree.CreatePartialFunction):
            self.output.ops.append(CreatePartialFunction(
                lineno, node.how_many_args))
            return

        if isinstance(node, decision_tree.SetMethodsToClass):
            self.output.ops.append(SetMethodsToClass(
                lineno, node.klass, node.how_many_methods))
            return

        raise NotImplementedError(repr(node))

    def opcode_tree(self, node):
        while node is not None:
            if node in self.jump_cache:
                self.output.ops.append(Jump(None, self.jump_cache[node]))
                break

            lineno = self._lineno(node.location)
            if len(node.jumped_from) > 1:
                marker = JumpMarker()
                self.jump_cache[node] = marker
                self.output.ops.append(marker)

            if isinstance(node, decision_tree.PassThroughNode):
                self.opcode_passthroughnode(node)
                node = node.next_node

            elif isinstance(node, decision_tree.TwoWayDecision):
                # this does not output the same bytecode twice
                # for example, consider this code
                #
                #    a
                #    if b:
                #        c
                #    else:
                #        d
                #    e
                #
                # it creates a tree like this
                #
                #     a
                #     |
                #     b
                #    / \
                #   c   d
                #    \ /
                #     e
                #
                # and opcode like this
                #
                #    a
                #    b
                #    if b is true, jump to then_marker
                #    d
                #    e
                #    jump to done_marker
                #    then_marker
                #    c
                #    jump to e
                #    done_marker
                #
                # the 'jump to e' part gets added by jump_cache stuff, because
                # e has already gotten opcoded once and can be reused
                #
                # this is not ideal, could be pseudo-optimized to do less
                # jumps, but that is likely not a bottleneck so why bother
                then_marker = JumpMarker()
                done_marker = JumpMarker()

                if isinstance(node, decision_tree.BoolDecision):
                    self.output.ops.append(JumpIf(lineno, then_marker))
                elif isinstance(node, decision_tree.EqualDecision):
                    self.output.ops.append(JumpIfEqual(lineno, then_marker))
                else:
                    raise RuntimeError("oh no")         # pragma: no cover

                self.opcode_tree(node.otherwise)
                self.output.ops.append(Jump(None, done_marker))
                self.output.ops.append(then_marker)
                self.opcode_tree(node.then)
                self.output.ops.append(done_marker)
                break

            else:
                raise NotImplementedError(repr(node))


def create_opcode(compilation, root_node, export_vars, source_code):
    assert not export_vars      # TODO

    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    output = OpCode(decision_tree.get_max_stack_size(root_node))
    _OpCoder(output, compilation, line_start_offsets).opcode_tree(root_node)

    import pprint; pprint.pprint(output.ops)
    output.fix_none_linenos()
    return output
