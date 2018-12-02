import collections

from . import bytecode_reader, objects


_Scope = collections.namedtuple('Scope', 'local_vars parent_scopes')


def _create_subscope(parent_scope, how_many_local_vars):
    return _Scope([None] * how_many_local_vars,
                  parent_scope.parent_scopes + [parent_scope])


def _create_function_object(code, definition_scope):
    def python_func(*args):
        scope = _create_subscope(definition_scope, code.how_many_local_vars)
        for index, arg in enumerate(args):
            scope.local_vars[index] = arg
        _run(code, scope)

    return objects.Function(python_func)


def _run(code, scope):
    stack = []
    for opcode, *args in code.opcodes:
        if opcode == bytecode_reader.CONSTANT:
            stack.append(args[0])
        # TODO: two kinds of function calls, void and returning?
        elif opcode == bytecode_reader.CALL_FUNCTION:
            [how_many_args] = args
            # python's negative slices are dumb
            if how_many_args == 0:
                call_args = []
            else:
                call_args = stack[-how_many_args:]
                del stack[-how_many_args:]
            stack[-1] = stack[-1].run(call_args)
        elif opcode == bytecode_reader.LOOKUP_VAR:
            level, index = args
            if level == len(scope.parent_scopes):
                lookup_scope = scope
            else:
                lookup_scope = scope.parent_scopes[level]
            stack.append(lookup_scope.local_vars[index])
        elif opcode == bytecode_reader.SET_VAR:
            [index] = args
            scope.local_vars[index] = stack.pop()
        elif opcode == bytecode_reader.POP_ONE:
            del stack[-1]
        elif opcode == bytecode_reader.CREATE_FUNCTION:
            name, body = args
            stack.append(_create_function_object(body, scope))
        else:
            assert False, opcode

    assert not stack


def run_file(code):
    global_scope = _Scope(objects.BUILTINS, [])
    file_scope = _create_subscope(global_scope, code.how_many_local_vars)
    _run(code, file_scope)
