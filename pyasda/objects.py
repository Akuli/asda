class AsdaType:
    pass


types = {
    'Str': AsdaType(),
    'Int': AsdaType(),
}


class FunctionType(AsdaType):

    def __init__(self, argtypes, returntype):
        self.argtypes = list(argtypes)
        self.returntype = returntype

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented
        return (self.argtypes == other.argtypes and
                self.returntype == other.returntype)


class AsdaObject:

    def __init__(self, asda_type):
        self.asda_type = asda_type


class AsdaString(AsdaObject):

    def __init__(self, python_string):
        super().__init__(types['Str'])
        self.python_string = python_string

    def __repr__(self):
        return '<%s.%s: %r>' % (type(self).__module__, type(self).__name__,
                                self.python_string)


class Function(AsdaObject):

    def __init__(self, argtypes, returntype, python_func):
        super().__init__(FunctionType(argtypes, returntype))
        self.python_func = python_func

    def run(self, args):
        return self.python_func(*args)


BUILTINS = [
    Function([types['Str']], None,
             lambda arg: print(arg.python_string)),
]
