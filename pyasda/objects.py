# right now this file looks like a skeleton of boilerplate, but it works


class AsdaType:
    pass


types = {
    'Str': AsdaType(),
    'Int': AsdaType(),
    'Bool': AsdaType(),
}


# TODO: keep track of arg types and return type?
class FunctionType(AsdaType):
    pass


# TODO: keep track of item types?
class GeneratorType(AsdaType):
    pass


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

    def __init__(self, next_callback):
        super().__init__(GeneratorType())
        self.next = next_callback


class Function(AsdaObject):

    def __init__(self, python_func):
        super().__init__(FunctionType())
        self.python_func = python_func

    def run(self, args):
        return self.python_func(*args)


TRUE = AsdaObject(types['Bool'])
FALSE = AsdaObject(types['Bool'])

BUILTINS = [
    Function(lambda arg: print(arg.python_string)),
    TRUE,
    FALSE,
    Function(lambda arg: arg.next()),
]
