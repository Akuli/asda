import collections
import enum
import os

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


def _create_function_object(definition_scope, modules, tybe, name, code,
                            yields):
    def python_func(*args):
        scope = _create_subscope(definition_scope, code.how_many_local_vars)
        for index, arg in enumerate(args):
            scope.local_vars[index] = arg
        runner = _Runner(code, scope, modules)

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

    def __init__(self, code, scope, modules):
        self.scope = scope
        self.stack = []
        self.opcodes = more_itertools.seekable(code.opcodes)
        self.opcodes_len = len(code.opcodes)
        self.modules = modules

    # returns (RunResult, value) where value is one of:
    #   * yielded value
    #   * returned value
    #   * None for void return
    def run(self):
        for lineno, opcode, args in self.opcodes:
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
                self.stack.append(_create_function_object(
                    self.scope, self.modules, *args))

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

            elif opcode == bytecode_reader.LOOKUP_ATTRIBUTE:
                [tybe, index] = args
                self.stack[-1] = tybe.get_attribute(self.stack[-1], index)

            elif opcode == bytecode_reader.DIDNT_RETURN_ERROR:
                raise ValueError("a non-void function didn't return")

            elif opcode == bytecode_reader.STR_JOIN:
                [how_many] = args
                assert how_many >= 2
                strings = self.stack[-how_many:]
                self.stack[-how_many:] = [
                    objects.String(''.join(s.python_string for s in strings))]

            elif opcode == bytecode_reader.PREFIX_MINUS:
                self.stack[-1] = self.stack[-1].prefix_minus()

            elif opcode == bytecode_reader.LOOKUP_MODULE:
                [path] = args
                assert self.modules[path] is not None
                self.stack.append(self.modules[path])

            elif opcode in {bytecode_reader.PLUS, bytecode_reader.MINUS,
                            bytecode_reader.TIMES,  # bytecode_reader.DIVIDE,
                            bytecode_reader.EQUAL}:
                rhs = self.stack.pop()
                lhs = self.stack.pop()

                if opcode == bytecode_reader.PLUS:
                    self.stack.append(lhs.plus(rhs))
                elif opcode == bytecode_reader.MINUS:
                    self.stack.append(lhs.minus(rhs))
                elif opcode == bytecode_reader.TIMES:
                    self.stack.append(lhs.times(rhs))
#                elif opcode == bytecode_reader.DIVIDE:
#                    self.stack.append(lhs.divide(rhs))
                elif opcode == bytecode_reader.EQUAL:
                    self.stack.append(lhs.equal(rhs))
                else:
                    assert False, opcode

            else:
                assert False, opcode

        assert not self.stack
        return (RunResult.DIDNT_RETURN, None)


class Interpreter:

    def __init__(self):
        self.modules = {}
        self.global_scope = _Scope(objects.BUILTINS, [])

    def import_path(self, path):
        path = os.path.abspath(path)

        if path in self.modules:
            return self.modules[path]

        with open(path, 'rb') as file:
            generator = bytecode_reader.read_bytecode(path, file)
            imports = next(generator)
            for path_to_import in imports:
                self.import_path(path_to_import)
            opcode = generator.send(self.modules)

        file_scope = _create_subscope(self.global_scope,
                                      opcode.how_many_local_vars)
        result = _Runner(opcode, file_scope, self.modules).run()
        assert result == (RunResult.DIDNT_RETURN, None), result

        # file_scope.local_vars contains more stuff than just the exports, but
        # the exports are guaranteed to be first
        module = objects.Object(objects.ModuleType(path, file_scope.local_vars)
                                )
        self.modules[path] = module
