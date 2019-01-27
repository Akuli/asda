import collections
import enum

import more_itertools

from . import bytecode_reader, objects


_Scope = collections.namedtuple('Scope', 'local_vars parent_scopes')


def _create_subscope(parent_scope, how_many_local_vars):
    return _Scope([None] * how_many_local_vars,
                  parent_scope.parent_scopes + [parent_scope])


class RunResult(enum.Enum):
    YIELDED = 1
    VALUE_RETURNED = 2
    VOID_RETURNED = 3
    DIDNT_RETURN = 4


def _create_function_object(definition_scope, tybe, name, code, yields):
    def python_func(*args):
        scope = _create_subscope(definition_scope, code.how_many_local_vars)
        for index, arg in enumerate(args):
            scope.local_vars[index] = arg
        runner = _Runner(code, scope)

        if not yields:
            result, value = runner.run()
            assert result in {RunResult.VALUE_RETURNED,
                              RunResult.VOID_RETURNED}
            return value

        def get_next_item():
            result, value = runner.run()
            if result == RunResult.YIELDED:
                assert value is not None
                return value

            if result == RunResult.VOID_RETURNED:
                # end of iteration
                assert value is None
                raise RuntimeError("iteration ended lel")

            assert False, result

        return objects.Generator(tybe.returntype, get_next_item)

    return objects.Function(tybe, name, python_func)


class _Runner:

    def __init__(self, code, scope):
        self.scope = scope
        self.stack = []
        self.opcodes = more_itertools.seekable(code.opcodes)
        self.opcodes_len = len(code.opcodes)

    # returns (RunResult, value) where value is one of:
    #   * yielded value
    #   * returned value
    #   * None for void return
    def run(self):
        for opcode, *args in self.opcodes:
            if opcode == bytecode_reader.CONSTANT:
                [constant] = args
                self.stack.append(constant)

            elif opcode in {bytecode_reader.CALL_VOID_FUNCTION,
                            bytecode_reader.CALL_RETURNING_FUNCTION}:
                [how_many_args] = args

                # python's negative slices are dumb
                if how_many_args == 0:
                    call_args = []
                else:
                    call_args = self.stack[-how_many_args:]
                    del self.stack[-how_many_args:]

                if opcode == bytecode_reader.CALL_RETURNING_FUNCTION:
                    self.stack[-1] = self.stack[-1].run(call_args)
                else:
                    self.stack.pop().run(call_args)

            elif opcode == bytecode_reader.LOOKUP_VAR:
                level, index = args
                if level == len(self.scope.parent_scopes):
                    var_scope = self.scope
                else:
                    var_scope = self.scope.parent_scopes[level]

                if var_scope.local_vars[index] is None:
                    raise RuntimeError(
                        "the value of a variable hasn't been set")

                self.stack.append(var_scope.local_vars[index])

            elif opcode == bytecode_reader.SET_VAR:
                level, index = args
                if level == len(self.scope.parent_scopes):
                    var_scope = self.scope
                else:
                    var_scope = self.scope.parent_scopes[level]
                var_scope.local_vars[index] = self.stack.pop()

            elif opcode == bytecode_reader.POP_ONE:
                del self.stack[-1]

            elif opcode == bytecode_reader.CREATE_FUNCTION:
                self.stack.append(_create_function_object(self.scope, *args))

            elif opcode == bytecode_reader.VOID_RETURN:
                assert not self.stack
                return (RunResult.VOID_RETURNED, None)

            elif opcode == bytecode_reader.VALUE_RETURN:
                value = self.stack.pop()
                assert not self.stack
                return (RunResult.VALUE_RETURNED, value)

            elif opcode == bytecode_reader.YIELD:
                value = self.stack.pop()
                return (RunResult.YIELDED, value)

            elif opcode == bytecode_reader.NEGATION:
                self.stack[-1] = {objects.TRUE: objects.FALSE,
                                  objects.FALSE: objects.TRUE}[self.stack[-1]]

            elif opcode == bytecode_reader.JUMP_IF:
                [opcode_index] = args
                boolean = self.stack.pop()
                assert boolean is objects.TRUE or boolean is objects.FALSE
                if boolean is objects.TRUE:
                    assert 0 <= opcode_index <= self.opcodes_len
                    self.opcodes.seek(opcode_index)

            elif opcode == bytecode_reader.LOOKUP_METHOD:
                [tybe, index] = args
                unbound = tybe.methods[index]
                self.stack[-1] = unbound.method_bind(self.stack[-1])

            elif opcode == bytecode_reader.DIDNT_RETURN_ERROR:
                raise ValueError("a non-void function didn't return")

            elif opcode == bytecode_reader.STR_JOIN:
                [how_many] = args
                assert how_many >= 2
                strings = self.stack[-how_many:]
                self.stack[-how_many:] = [
                    objects.String(''.join(s.python_string for s in strings))]

            else:
                assert False, opcode

        assert not self.stack
        return (RunResult.DIDNT_RETURN, None)


def run_file(code):
    global_scope = _Scope(objects.BUILTINS, [])
    file_scope = _create_subscope(global_scope, code.how_many_local_vars)
    result = _Runner(code, file_scope).run()
    assert result == (RunResult.DIDNT_RETURN, None), result
