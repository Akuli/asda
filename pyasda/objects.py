# right now this file looks like a skeleton of boilerplate, but it works

import collections


class AsdaType:
    pass


types = collections.OrderedDict([
    ('Str', AsdaType()),
    ('Int', AsdaType()),
    ('Bool', AsdaType()),
])


class GenericType(AsdaType):
    pass


class FunctionType(AsdaType):

    def __init__(self, argtypes, returntype, is_generator=False):
        super().__init__()
        self.argtypes = argtypes
        self.returntype = returntype
        self.is_generator = is_generator


class GeneratorType(AsdaType):

    def __init__(self, itemtype):
        super().__init__()
        self.itemtype = itemtype


class AsdaObject:

    def __init__(self, asda_type):
        self.asda_type = asda_type


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

    def run(self, args):
        assert len(args) == len(self.asda_type.argtypes)
        for arg, tybe in zip(args, self.asda_type.argtypes):
            pass   # TODO: how 2 check this
        return self.python_func(*args)


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
