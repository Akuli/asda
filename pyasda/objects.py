class AsdaType:
    pass


types = {
    'Str': AsdaType(),
    'Int': AsdaType(),
    'Bool': AsdaType(),
}


# TODO: keep track of arg types and return type
class FunctionType(AsdaType):
    pass


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

    def __init__(self, python_func):
        super().__init__(FunctionType())
        self.python_func = python_func

    def run(self, args):
        return self.python_func(*args)


BUILTINS = [
    Function(lambda arg: print(arg.python_string)),
    types['Bool'],      # TRUE
    types['Bool'],      # FALSE
]
