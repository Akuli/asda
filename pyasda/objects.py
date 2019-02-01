# right now this file looks like a skeleton of boilerplate, but it works

import collections
import functools
import itertools


class Type:

    def __init__(self, base):
        self.methods = []
        self.base_type = base   # None for OBJECT


OBJECT = Type(None)     # the asda base class of all asda objects


class Object:       # the python base class of all asda objects

    def __init__(self, tybe):
        self.type = tybe


class FunctionType(Type):

    def __init__(self, argtypes, returntype):
        super().__init__(OBJECT)
        self.argtypes = list(argtypes)
        self.returntype = returntype


class Function(Object):

    def __init__(self, tybe, name, python_func):
        super().__init__(tybe)
        self.name = name
        self.python_func = python_func

    def method_bind(self, this):
        bound_type = FunctionType(self.type.argtypes[1:], self.type.returntype)
        return Function(bound_type, self.name,
                        functools.partial(self.python_func, this))

    def run(self, args):
        assert len(args) == len(self.type.argtypes)
        return self.python_func(*args)


def add_method(tybe, name, python_func, argtypes, returntype):
    functype = FunctionType(itertools.chain([tybe], argtypes), returntype)
    tybe.methods.append(Function(functype, name, python_func))


types = collections.OrderedDict([
    ('Str', Type(OBJECT)),
    ('Int', Type(OBJECT)),
    ('Bool', Type(OBJECT)),
    ('Object', OBJECT),
])

add_method(
    types['Str'], 'uppercase',
    (lambda this: String(this.python_string.upper())), [], types['Str'])
add_method(types['Str'], 'to_string', (lambda this: this), [], types['Str'])
add_method(
    types['Int'], 'to_string',
    (lambda this: String(str(this.python_int))), [], types['Str'])


class GenericType(Type):

    def __init__(self):
        super().__init__(OBJECT)


class GeneratorType(Type):

    def __init__(self, itemtype):
        super().__init__(OBJECT)
        self.itemtype = itemtype


class String(Object):

    def __init__(self, python_string):
        super().__init__(types['Str'])
        self.python_string = python_string

    def __repr__(self):
        return '<%s.%s: %r>' % (type(self).__module__, type(self).__name__,
                                self.python_string)


INT64_MIN = -2**63
INT64_MAX = 2**63 - 1


class Integer(Object):
    def __init__(self, python_int):
        super().__init__(types['Int'])
        self.python_int = python_int


class Generator(Object):

    def __init__(self, tybe, next_callback):
        assert isinstance(tybe, GeneratorType)
        super().__init__(tybe)
        self.next = next_callback


TRUE = Object(types['Bool'])
FALSE = Object(types['Bool'])

T = GenericType()
BUILTINS = [
    Function(FunctionType([types['Str']], None), 'print',
             lambda arg: print(arg.python_string)),
    TRUE,
    FALSE,
    Function(FunctionType([GeneratorType(T)], T), 'next',
             lambda arg: arg.next()),
]
del T
