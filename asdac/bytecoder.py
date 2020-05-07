# converts decision tree to bytes that can be written to file

import bisect
import collections
import functools
import io
import os

from asdac import common, cooked_ast, decision_tree, objects


SET_LINENO = b'L'

GET_BUILTIN_VAR = b'U'
SET_ATTR = b':'
GET_ATTR = b'.'
GET_FROM_MODULE = b'm'
FUNCTION_BEGINS = b'f'
STR_CONSTANT = b'"'
NON_NEGATIVE_INT_CONSTANT = b'1'
NEGATIVE_INT_CONSTANT = b'2'
CALL_BUILTIN_FUNCTION = b'b'
CALL_THIS_FILE_FUNCTION = b'('
STR_JOIN = b'j'
POP_ONE = b'P'
THROW = b't'
YIELD = b'Y'
SET_METHODS_TO_CLASS = b'S'
RETURN = b'r'

JUMP = b'K'
JUMP_IF = b'J'
JUMP_IF_INT_EQUAL = b'='
JUMP_IF_STR_EQUAL = b'q'

PLUS = b'+'
MINUS = b'-'
PREFIX_MINUS = b'_'
TIMES = b'*'
# DIVIDE = b'/'

EXPORT_OBJECT = b'x'

# these are used when bytecoding a type
TYPE_ASDA_CLASS = b'a'
TYPE_BUILTIN = b'b'
TYPE_FUNCTION = b'f'
TYPE_VOID = b'v'

IMPORT_SECTION = b'i'
EXPORT_SECTION = b'e'
TYPE_LIST_SECTION = b'y'


def _bit_storing_size(n):
    """Returns the number of bytes needed for storing n bits.

    >>> _bit_storing_size(16)
    2
    >>> _bit_storing_size(17)
    3
    """
    return -((-n) // 8)


def _attribute_name_to_index(tybe, name):
    assert isinstance(tybe.attributes, collections.OrderedDict)
    return list(tybe.attributes.keys()).index(name)


# sometimes it's necessary to change an uint after adding it to bytecode
class _UintInByteCode:

    def __init__(self, byte_array, offset, size):
        self._byte_array = byte_array
        self._offset = offset
        self._size = size

    def set(self, number):
        try:
            bytez = number.to_bytes(self._size, 'little')
        except OverflowError:
            raise common.CompileError(
                "this number does not fit in an unsigned %d-bit integer: %d"
                % (self._size * 8, number))

        self._byte_array[self._offset:self._offset+self._size] = bytez


class _ByteCodeCreator:

    def __init__(self, byte_array, compilation,
                 line_start_offsets, current_lineno, argvars):
        self.byte_array = byte_array
        self.compilation = compilation
        self.line_start_offsets = line_start_offsets
        self.current_lineno = current_lineno
        self.argvars = argvars
        self.stack_sizes = {}

        # because functions may need to be referred to before they are written
        self.function_references = {}   # Function --> uint16 in byte code
        self.function_definitions = {}  # Function --> value to set to uint16

        self.op_index = 0     # number of ops written so far, file specific
        self.jump_cache = {}  # keys are nodes, values are op_index values

    def _write_uint(self, bits, number):
        r"""
        >>> bc = _ByteCode()
        >>> bc.write_uint16(1)
        >>> bc.get_bytes()
        b'\x01\x00'
        """
        assert bits % 8 == 0 and 0 < bits <= 64, bits

        result = _UintInByteCode(
            self.byte_array, len(self.byte_array), bits // 8)
        result.set(number)   # this makes self.byte_array longer
        return result

    write_uint8 = functools.partialmethod(_write_uint, 8)
    write_uint16 = functools.partialmethod(_write_uint, 16)
    write_uint32 = functools.partialmethod(_write_uint, 32)

    def write_big_uint(self, abs_value):
        assert abs_value >= 0
        size = _bit_storing_size(abs_value.bit_length())
        self.write_uint32(size)
        self.byte_array.extend(abs_value.to_bytes(size, 'little'))

    def write_string(self, string):
        utf8 = string.encode('utf-8')
        self.write_uint32(len(utf8))
        self.byte_array.extend(utf8)

    def write_path(self, path):
        relative2 = self.compilation.compiled_path.parent
        relative_path = common.relpath(path, relative2)

        # asda-compiled/whatever.asdac should always be in lowercase, and other
        # code should ensure that
        assert str(relative_path).islower()

        # forward slash to make the compiled bytecodes cross-platform
        self.write_string(str(relative_path).replace(os.sep, '/'))

    # returns line number so that 1 means first line
    def _set_lineno(self, location):
        if location is None:
            return

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
        lineno = bisect.bisect(self.line_start_offsets, location.offset)
        if lineno != self.current_lineno:
            self.byte_array.extend(SET_LINENO)
            self.write_uint32(lineno)
            self.current_lineno = lineno

    def _is_builtin_generic_type(self, tybe):
        return (
            tybe.original_generic is not None and
            tybe.original_generic in objects.BUILTIN_GENERIC_TYPES.values())

    def write_type(self, tybe, *, allow_void=False):
        if tybe is None:
            assert allow_void
            self.byte_array.extend(TYPE_VOID)
            return

        assert (tybe in objects.BUILTIN_TYPES.values() or
                self._is_builtin_generic_type(tybe))

        if tybe in objects.BUILTIN_TYPES.values():
            names = list(objects.BUILTIN_TYPES)
            self.byte_array.extend(TYPE_BUILTIN)
            self.write_uint8(names.index(tybe.name))
        elif self._is_builtin_generic_type(tybe):
            # interpreter doesn't know anything about generic types
            # it has all built-in types in the same array
            # generics are there last
            lizt = list(objects.BUILTIN_GENERIC_TYPES.values())
            index = lizt.index(tybe.original_generic)
            self.byte_array.extend(TYPE_BUILTIN)
            self.write_uint8(len(objects.BUILTIN_TYPES) + index)
        elif isinstance(tybe, objects.GenericMarker):
            self.write_type(objects.BUILTIN_TYPES['Object'])
        else:
            assert False, tybe      # pragma: no cover

    def write_opbyte(self, byte):
        assert len(byte) == 1
        self.byte_array.extend(byte)
        self.op_index += 1

    def write_pass_through_node(self, node):
        if isinstance(node, decision_tree.StrConstant):
            self.write_opbyte(STR_CONSTANT)
            self.write_string(node.python_string)
            return

        if isinstance(node, decision_tree.IntConstant):
            if node.python_int >= 0:
                self.write_opbyte(NON_NEGATIVE_INT_CONSTANT)
                self.write_big_uint(node.python_int)
            else:
                # currently this code never runs because -2 is parsed as the
                # prefix minus operator applied to the non-negative integer
                # constant 2, but i'm planning on adding an optimizer that
                # would output it as a thing that needs this code
                self.write_opbyte(NEGATIVE_INT_CONSTANT)
                self.write_big_uint(abs(node.python_int))
            return

        if isinstance(node, decision_tree.GetBuiltinVar):
            self.write_opbyte(GET_BUILTIN_VAR)
            names = list(objects.BUILTIN_VARS.keys())
            self.write_uint8(names.index(node.varname))
            return

        if isinstance(node, decision_tree.CallFunction):
            if node.function.kind == cooked_ast.FunctionKind.BUILTIN:
                self.write_opbyte(CALL_BUILTIN_FUNCTION)
                # TODO: identify the function somehow instead of assuming that
                #       it's print
            elif node.function.kind == cooked_ast.FunctionKind.FILE:
                self.write_opbyte(CALL_THIS_FILE_FUNCTION)
                refs = self.function_references.setdefault(node.function, [])
                refs.append(self.write_uint16(0))
            else:
                raise NotImplementedError

            self.write_uint16(node.how_many_args)
            return

        if isinstance(node, (decision_tree.GetAttr, decision_tree.SetAttr)):
            self.write_opbyte(
                GET_ATTR if isinstance(node, decision_tree.GetAttr)
                else SET_ATTR)
            self.write_type(node.tybe)
            self.write_uint16(
                _attribute_name_to_index(node.tybe, node.attrname))
            return

        if isinstance(node, decision_tree.StrJoin):
            self.write_opbyte(STR_JOIN)
            self.write_uint16(node.how_many_strings)
            return

        simple_things = [
            (decision_tree.PopOne, POP_ONE),
            (decision_tree.Plus, PLUS),
            (decision_tree.Minus, MINUS),
            (decision_tree.PrefixMinus, PREFIX_MINUS),
            (decision_tree.Times, TIMES),
            # (decision_tree.Divide, DIVIDE),
        ]

        for klass, byte in simple_things:
            if isinstance(node, klass):
                self.write_opbyte(byte)
                return

        assert False, node        # pragma: no cover

    def write_2_way_decision(self, node):
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
        # the 'jump to e' part gets added by jump_cache stuff, because e has
        # already gotten opcoded once and can be reused
        #
        # this is not ideal, could be pseudo-optimized to do less jumps, but
        # that's likely not a bottleneck so why bother

        if isinstance(node, decision_tree.BoolDecision):
            self.write_opbyte(JUMP_IF)
        elif isinstance(node, decision_tree.IntEqualDecision):
            self.write_opbyte(JUMP_IF_INT_EQUAL)
        elif isinstance(node, decision_tree.StrEqualDecision):
            self.write_opbyte(JUMP_IF_STR_EQUAL)
        else:  # pragma: no cover
            raise RuntimeError
        then_jump = self.write_uint16(0)

        self.write_tree(node.otherwise)

        self.write_opbyte(JUMP)
        done_jump = self.write_uint16(0)

        then_jump.set(self.op_index)
        self.write_tree(node.then)
        done_jump.set(self.op_index)

    def write_tree(self, node: decision_tree.Node):
        while node is not None:
            if node in self.jump_cache:
                self.write_opbyte(JUMP)
                self.write_uint16(self.jump_cache[node])
                return

            if len(node.jumped_from) > 1:
                self.jump_cache[node] = self.op_index

            self._set_lineno(node.location)
            if isinstance(node, decision_tree.PassThroughNode):
                self.write_pass_through_node(node)
                node = node.next_node
            elif isinstance(node, decision_tree.TwoWayDecision):
                self.write_2_way_decision(node)
                return
            else:
                raise NotImplementedError("omg " + repr(node))

        self.write_opbyte(RETURN)

    def write_function_opcode(self, function: cooked_ast.Function, start_node):
        assert function.kind == cooked_ast.FunctionKind.FILE
        self.function_definitions[function] = self.op_index

        op_count = self.write_uint16(0)
        old_op_index = self.op_index
        self.write_opbyte(FUNCTION_BEGINS)
        self.write_uint16(decision_tree.get_max_stack_size(start_node))
        self.write_tree(start_node.next_node)
        op_count.set(self.op_index - old_op_index)

    def fix_function_references(self):
        for func, refs in self.function_references.items():
            for ref in refs:
                ref.set(self.function_definitions[func])


def _swap_bytes(byte_array, start, middle):
    """Swaps byte_array[start:middle] and byte_array[middle:] with each other.

    >>> b = bytearray(b'ABCde1234')
    >>> _swap_bytes(b, 3, 5)
    >>> b
    bytearray(b'ABC1234de')
    """
    temp = byte_array[middle:]
    del byte_array[middle:]
    byte_array[start:start] = temp


# structure of a bytecode file:
#   1.  the bytes b'asda\xA5\xDA'  (note how 5 looks like S, lol)
#   2.  source path string, relative to the dirname of the compiled path
#   3.  opcode of each function
#
# all paths are relative to the bytecode file's directory and have '/' as
# the separator
def create_bytecode(compilation, function_trees, source_code):
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    # make sure that main is first
    funclist = sorted(function_trees.keys(),
                      key=(lambda f: 1 if f.is_main else 2))
    assert funclist[0].is_main
    if len(funclist) >= 2:
        assert not funclist[1].is_main

    creator = _ByteCodeCreator(
        bytearray(), compilation, line_start_offsets, 1, [])

    creator.byte_array.extend(b'asda\xA5\xDA')
    creator.write_path(compilation.source_path)
    creator.write_uint16(len(function_trees))

    for func in funclist:
        creator.write_function_opcode(func, function_trees[func])
    creator.fix_function_references()

    return creator.byte_array
