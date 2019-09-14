# converts decision tree to bytes that can be written to file

import bisect
import collections
import functools
import io
import os

from asdac import common, decision_tree, objects


SET_LINENO = b'L'

GET_BUILTIN_VAR = b'U'
SET_LOCAL_VAR = b'B'    # B for historical reasons
GET_LOCAL_VAR = b'b'
SET_ATTR = b':'
GET_ATTR = b'.'
GET_FROM_MODULE = b'm'
CREATE_FUNCTION = b'f'
CREATE_PARTIAL_FUNCTION = b'p'
CREATE_BOX = b'0'
SET_TO_BOX = b'O'
UNBOX = b'o'
STR_CONSTANT = b'"'
NON_NEGATIVE_INT_CONSTANT = b'1'
NEGATIVE_INT_CONSTANT = b'2'
CALL_FUNCTION = b'('
CALL_CONSTRUCTOR = b')'
STR_JOIN = b'j'
POP_ONE = b'P'
STORE_RETURN_VALUE = b'R'
THROW = b't'
YIELD = b'Y'
SET_METHODS_TO_CLASS = b'S'
END_OF_BODY = b'E'

JUMP = b'K'
JUMP_IF = b'J'
JUMP_IF_EQUAL = b'='

PLUS = b'+'
MINUS = b'-'
PREFIX_MINUS = b'_'
TIMES = b'*'
# DIVIDE = b'/'

ADD_ERROR_HANDLER = b'h'
REMOVE_ERROR_HANDLER = b'H'

PUSH_FINALLY_STATE_OK = b'3'
PUSH_FINALLY_STATE_ERROR = b'4'
# b'5' skipped for historical reasons
PUSH_FINALLY_STATE_VALUE_RETURN = b'6'
PUSH_FINALLY_STATE_JUMP = b'7'

APPLY_FINALLY_STATE = b'A'
DISCARD_FINALLY_STATE = b'D'

EXPORT_OBJECT = b'x'


# these are used when bytecoding a type
TYPE_ASDA_CLASS = b'a'
TYPE_BUILTIN = b'b'
TYPE_FUNCTION = b'f'
TYPE_VOID = b'v'
TYPE_FROM_LIST = b'l'

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


def _local_vars_to_list(start_node, local_vars_list):
    for node in decision_tree.get_all_nodes(start_node):
        if isinstance(node, (decision_tree.SetLocalVar,
                             decision_tree.GetLocalVar)):
            # O(n) 'not in' check but there shouldn't be many local vars
            if node.var not in local_vars_list:
                local_vars_list.append(node.var)


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

    def __init__(self, byte_array, compilation, line_start_offsets,
                 current_lineno, type_list):
        self.byte_array = byte_array
        self.compilation = compilation
        self.line_start_offsets = line_start_offsets
        self.current_lineno = current_lineno

        # when the interpreter imports the bytecode file, it creates things
        # that represent these types, and looks up these types by index
        self.type_list = type_list

        self.local_vars = []
        self.op_index = 0       # number of ops written so far, for jumps
        self.jump_cache = {}    # keys are nodes, values are op_index values

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

    def _ensure_type_is_in_type_list_if_needed(self, tybe):
        assert tybe is not None
        if (
          tybe in self.type_list or
          tybe in objects.BUILTIN_TYPES.values() or
          self._is_builtin_generic_type(tybe)):
            return

        if isinstance(tybe, objects.FunctionType):
            for argtype in tybe.argtypes:
                self._ensure_type_is_in_type_list_if_needed(argtype)
            if tybe.returntype is not None:
                self._ensure_type_is_in_type_list_if_needed(tybe.returntype)
        elif isinstance(tybe, objects.UserDefinedClass):
            # TODO: remember to change this when argtypes and class members
            #       become different things
            for argtybe in tybe.constructor_argtypes:
                self._ensure_type_is_in_type_list_if_needed(argtybe)
        else:
            assert False, tybe      # pragma: no cover

        self.type_list.append(tybe)

    def write_type(self, tybe, *, allow_void=False):
        if tybe is None:
            assert allow_void
            self.byte_array.extend(TYPE_VOID)
            return

        self._ensure_type_is_in_type_list_if_needed(tybe)

        if tybe in self.type_list:
            self.byte_array.extend(TYPE_FROM_LIST)
            self.write_uint16(self.type_list.index(tybe))
        elif tybe in objects.BUILTIN_TYPES.values():
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
        else:
            assert False, tybe      # pragma: no cover

    # call this after run()
    def write_type_list(self):
        self.byte_array.extend(TYPE_LIST_SECTION)
        self.write_uint16(len(self.type_list))

        for tybe in self.type_list:
            if isinstance(tybe, objects.FunctionType):
                self.byte_array.extend(TYPE_FUNCTION)
                self.write_type(tybe.returntype, allow_void=True)

                self.write_uint8(len(tybe.argtypes))
                for argtype in tybe.argtypes:
                    self.write_type(argtype)

            elif isinstance(tybe, objects.UserDefinedClass):
                self.byte_array.extend(TYPE_ASDA_CLASS)
                self.write_uint16(len(tybe.constructor_argtypes))
                self.write_uint16(
                    len(tybe.attributes) - len(tybe.constructor_argtypes))

            else:   # pragma: no cover
                raise NotImplementedError(repr(tybe))

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

        if isinstance(node, decision_tree.CreateFunction):
            assert isinstance(node.functype, objects.FunctionType)
            self.write_opbyte(CREATE_FUNCTION)
            self.write_type(node.functype)

            creator = _ByteCodeCreator(
                self.byte_array, self.compilation, self.line_start_offsets,
                self.current_lineno, self.type_list)
            creator.local_vars.extend(node.local_argvars)
            creator.run(node.body_root_node)
            return

        if isinstance(node, decision_tree.CreatePartialFunction):
            self.write_opbyte(CREATE_PARTIAL_FUNCTION)
            self.write_uint16(node.how_many_args)
            return

        if isinstance(node, decision_tree.GetBuiltinVar):
            self.write_opbyte(GET_BUILTIN_VAR)
            names = list(objects.BUILTIN_VARS.keys())
            self.write_uint8(names.index(node.varname))
            return

        if isinstance(node, decision_tree.CallFunction):
            self.write_opbyte(CALL_FUNCTION)
            self.write_uint8(node.how_many_args)  # TODO: bigger than u8
            return

        if isinstance(node, decision_tree.CallConstructor):
            self.write_opbyte(CALL_CONSTRUCTOR)
            self.write_type(node.tybe)
            self.write_uint8(node.how_many_args)  # TODO: bigger than u8
            return

        if isinstance(node, decision_tree.StoreReturnValue):
            self.write_opbyte(STORE_RETURN_VALUE)
            return

        if isinstance(node, (decision_tree.GetAttr, decision_tree.SetAttr)):
            self.write_opbyte(
                GET_ATTR if isinstance(node, decision_tree.GetAttr) else SET_ATTR)
            self.write_type(node.tybe)
            self.write_uint16(
                _attribute_name_to_index(node.tybe, node.attrname))
            return

        if isinstance(node, decision_tree.StrJoin):
            self.write_opbyte(STR_JOIN)
            self.write_uint16(node.how_many_strings)
            return

        # FIXME: is very outdated
#        if isinstance(node, decision_tree.AddErrorHandler):
#            self.write_opbyte(ADD_ERROR_HANDLER)
#            self.write_uint16(len(node.items))
#            for jumpto_marker, errortype, errorvarlevel, errorvar in node.items:
#                self.write_type(errortype)
#                self.write_uint16(
#                    varlists[errorvarlevel].index(errorvar))
#                self.write_uint16(self.jumpmarker2index[jumpto_marker])
#            return
#
#        if isinstance(node, decision_tree.PushFinallyStateReturn):
#            self.write_opbyte(PUSH_FINALLY_STATE_VALUE_RETURN)
#            return
#
#        if isinstance(node, decision_tree.PushFinallyStateJump):
#            self.write_opbyte(PUSH_FINALLY_STATE_JUMP)
#            self.write_uint16(self.jumpmarker2index[node.index])
#            return

        if isinstance(node, decision_tree.SetMethodsToClass):
            self.write_opbyte(SET_METHODS_TO_CLASS)
            self.write_type(node.klass)
            self.write_uint16(node.how_many_methods)
            return

        if isinstance(node, decision_tree.SetLocalVar):
            self.write_opbyte(SET_LOCAL_VAR)
            self.write_uint16(self.local_vars.index(node.var))
            return

        if isinstance(node, decision_tree.GetLocalVar):
            self.write_opbyte(GET_LOCAL_VAR)
            self.write_uint16(self.local_vars.index(node.var))
            return

        if isinstance(node, decision_tree.ExportObject):
            self.write_opbyte(EXPORT_OBJECT)
            index = list(self.compilation.export_types.keys()).index(node.name)
            self.write_uint16(index)
            return

        if isinstance(node, decision_tree.GetFromModule):
            self.write_opbyte(GET_FROM_MODULE)
            self.write_uint16(
                self.compilation.imports.index(node.other_compilation))
            self.write_uint16(
                list(node.other_compilation.export_types.keys()).index(node.name))
            return

        simple_things = [
            (decision_tree.PopOne, POP_ONE),
            (decision_tree.Plus, PLUS),
            (decision_tree.Minus, MINUS),
            (decision_tree.PrefixMinus, PREFIX_MINUS),
            (decision_tree.Times, TIMES),
            # (decision_tree.Divide, DIVIDE),
            (decision_tree.CreateBox, CREATE_BOX),
            (decision_tree.SetToBox, SET_TO_BOX),
            (decision_tree.UnBox, UNBOX),
#            (decision_tree.RemoveErrorHandler, REMOVE_ERROR_HANDLER),
#            (decision_tree.PushFinallyStateOk, PUSH_FINALLY_STATE_OK),
#            (decision_tree.PushFinallyStateError, PUSH_FINALLY_STATE_ERROR),
#            (decision_tree.DiscardFinallyState, DISCARD_FINALLY_STATE),
#            (decision_tree.ApplyFinallyState, APPLY_FINALLY_STATE),
            (decision_tree.Throw, THROW),
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
        elif isinstance(node, decision_tree.EqualDecision):
            self.write_opbyte(JUMP_IF_EQUAL)
        else:  # pragma: no cover
            raise RuntimeError
        then_jump = self.write_uint16(0)

        self.write_tree(node.otherwise)

        self.write_opbyte(JUMP)
        done_jump = self.write_uint16(0)

        then_jump.set(self.op_index)
        self.write_tree(node.then)
        done_jump.set(self.op_index)

    def write_tree(self, node):
        while node is not None:
            if node in self.jump_cache:
                self.write_opbyte(JUMP)
                self.write_uint16(self.jump_cache[node])
                return

            if len(node.jumped_from) > 1:
                self.jump_cache[node] = self.op_index

            if isinstance(node, decision_tree.PassThroughNode):
                self.write_pass_through_node(node)
                node = node.next_node
            elif isinstance(node, decision_tree.TwoWayDecision):
                self.write_2_way_decision(node)
                return
            else:
                raise NotImplementedError("omg " + repr(node))

    def run(self, start_node):
        _local_vars_to_list(start_node, self.local_vars)
        self.write_uint16(len(self.local_vars))
        self.write_uint16(decision_tree.get_max_stack_size(start_node))
        self.write_tree(start_node.next_node)
        self.write_opbyte(END_OF_BODY)

    # this can be used to write either one of the two import sections
    def write_import_section(self, paths):
        self.byte_array.extend(IMPORT_SECTION)
        self.write_uint16(len(paths))
        for path in paths:
            self.write_path(path)

    def write_first_export_section(self, exports):
        assert isinstance(exports, collections.OrderedDict)
        self.byte_array.extend(EXPORT_SECTION)
        self.write_uint16(len(exports))

    def write_second_export_section(self, exports):
        self.write_first_export_section(exports)
        for name, tybe in exports.items():
            self.write_string(name)
            self.write_type(tybe)


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
#   3.  first import section: compiled file paths for the interpreter
#   4.  first export section: number of exports
#   5.  list of types used in the opcode
#   6.  opcode
#   7.  second import section: source file paths, for the compiler
#   8.  second export section: names and types, for the compiler
#   9.  number of bytes in opcode and everything before it, as an uint32.
#       The compiler uses this to efficiently read imports and exports.
#
# all paths are relative to the bytecode file's directory and have '/' as
# the separator
def create_bytecode(compilation, start_node, source_code):
    line_start_offsets = []
    offset = 0
    for line in io.StringIO(source_code):
        line_start_offsets.append(offset)
        offset += len(line)

    creator = _ByteCodeCreator(
        bytearray(), compilation, line_start_offsets, 1, [])

    creator.byte_array.extend(b'asda\xA5\xDA')
    creator.write_path(compilation.source_path)

    creator.write_import_section(
        [impcomp.compiled_path for impcomp in compilation.imports])
    creator.write_first_export_section(compilation.export_types)

    # interpreter wants type list before body opcode
    # it is much easier to create the opcode before the type list
    # so we do that and swap them afterwards
    start = len(creator.byte_array)
    creator.run(start_node)
    middle = len(creator.byte_array)
    creator.write_type_list()
    _swap_bytes(creator.byte_array, start, middle)
    after_opcode = len(creator.byte_array)

    creator.write_import_section(
        [impcomp.source_path for impcomp in compilation.imports])
    creator.write_second_export_section(compilation.export_types)

    creator.write_uint32(after_opcode)

    return creator.byte_array
