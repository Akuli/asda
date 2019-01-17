# right now this file looks like a skeleton of boilerplate, but it works

import collections
import functools
import itertools


class AsdaType:

    def __init__(self):
        self.methods = []


class GenericType(AsdaType):
    pass


class FunctionType(AsdaType):

    def __init__(self, argtypes, returntype, is_generator=False):
        super().__init__()
        self.argtypes = list(argtypes)
        self.returntype = returntype
        self.is_generator = is_generator


types = collections.OrderedDict([
    ('Str', AsdaType()),
    ('Int', AsdaType()),
    ('Bool', AsdaType()),
])


class GeneratorType(AsdaType):

    def __init__(self, itemtype):
        super().__init__()
        self.itemtype = itemtype


class AsdaObject:

    def __init__(self, asda_type):
        self.asda_type = asda_type      # TODO: rename to just 'type'


# TODO: rename this to String
class AsdaString(AsdaObject):

    def __init__(self, python_string):
        super().__init__(types['Str'])
        self.python_string = python_string

    def __repr__(self):
        return '<%s.%s: %r>' % (type(self).__module__, type(self).__name__,
                                self.python_string)


class Generator(AsdaObject):

    def __init__(self, tybe, next_callback):
        super().__init__(tybe)
        self.next = next_callback


class Function(AsdaObject):

    def __init__(self, tybe, python_func):
        super().__init__(tybe)
        self.python_func = python_func

    def method_bind(self, this):
        bound_type = FunctionType(self.asda_type.argtypes[1:],
                                  self.asda_type.returntype,
                                  self.asda_type.is_generator)
        return Function(bound_type, functools.partial(self.python_func, this))

    def run(self, args):
        assert len(args) == len(self.asda_type.argtypes)
        for arg, tybe in zip(args, self.asda_type.argtypes):
            pass   # TODO: how 2 check this
        return self.python_func(*args)


def add_method(tybe, python_func, argtypes, *args, **kwargs):
    functype = FunctionType(itertools.chain([tybe], argtypes), *args, **kwargs)
    tybe.methods.append(Function(functype, python_func))


add_method(
    types['Str'], (lambda this: AsdaString(this.python_string.upper())),
    [], types['Str'])


TRUE = AsdaObject(types['Bool'])
FALSE = AsdaObject(types['Bool'])

T = GenericType()
BUILTINS = [
    Function(FunctionType([types['Str']], None),
             lambda arg: print(arg.python_string)),
    TRUE,
    FALSE,
    Function(FunctionType([GeneratorType(T)], T), lambda arg: arg.next()),
]
del T
