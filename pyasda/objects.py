# right now this file looks like a skeleton of boilerplate, but it works

import collections
import functools
import itertools


class Type:

    def __init__(self):
        self.methods = []


class Object:

    def __init__(self, tybe):
        self.type = tybe


class FunctionType(Type):

    def __init__(self, argtypes, returntype):
        super().__init__()
        self.argtypes = list(argtypes)
        self.returntype = returntype


class Function(Object):

    def __init__(self, tybe, python_func):
        super().__init__(tybe)
        self.python_func = python_func

    def method_bind(self, this):
        bound_type = FunctionType(self.type.argtypes[1:], self.type.returntype)
        return Function(bound_type, functools.partial(self.python_func, this))

    def run(self, args):
        assert len(args) == len(self.type.argtypes)
        for arg, tybe in zip(args, self.type.argtypes):
            pass   # TODO: how 2 check this
        return self.python_func(*args)


def add_method(tybe, python_func, argtypes, *args, **kwargs):
    functype = FunctionType(itertools.chain([tybe], argtypes), *args, **kwargs)
    tybe.methods.append(Function(functype, python_func))


types = collections.OrderedDict([
    ('Str', Type()),
    ('Int', Type()),
    ('Bool', Type()),
])

add_method(
    types['Str'], (lambda this: String(this.python_string.upper())),
    [], types['Str'])


class GenericType(Type):
    pass


class GeneratorType(Type):

    def __init__(self, itemtype):
        super().__init__()
        self.itemtype = itemtype


class String(Object):

    def __init__(self, python_string):
        super().__init__(types['Str'])
        self.python_string = python_string

    def __repr__(self):
        return '<%s.%s: %r>' % (type(self).__module__, type(self).__name__,
                                self.python_string)


class Generator(Object):

    def __init__(self, tybe, next_callback):
        super().__init__(tybe)
        self.next = next_callback


TRUE = Object(types['Bool'])
FALSE = Object(types['Bool'])

T = GenericType()
BUILTINS = [
    Function(FunctionType([types['Str']], None),
             lambda arg: print(arg.python_string)),
    TRUE,
    FALSE,
    Function(FunctionType([GeneratorType(T)], T), lambda arg: arg.next()),
]
del T
