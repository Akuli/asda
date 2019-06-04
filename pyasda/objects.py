import collections
import functools
import itertools


class Type:

    def __init__(self, base):
        self._attributes = []   # (is_method, value) pairs
        self.base_type = base   # None for OBJECT

    def get_attribute(self, objekt, indeks):
        is_method, value = self._attributes[indeks]
        if is_method:
            # value is a Function
            return value.method_bind(objekt)
        return value


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

    def __init__(self, tybe, python_func):
        super().__init__(tybe)
        self.python_func = python_func

    def method_bind(self, this):
        bound_type = FunctionType(self.type.argtypes[1:], self.type.returntype)
        return Function(bound_type, functools.partial(self.python_func, this))

    def run(self, args):
        assert len(args) == len(self.type.argtypes)
        return self.python_func(*args)


def add_method(tybe, python_func, argtypes, returntype):
    functype = FunctionType(itertools.chain([tybe], argtypes), returntype)
    tybe._attributes.append((True, Function(functype, python_func)))


types = collections.OrderedDict([
    ('Str', Type(OBJECT)),
    ('Int', Type(OBJECT)),
    ('Bool', Type(OBJECT)),
    ('Object', OBJECT),
])

# Str.uppercase
add_method(
    types['Str'], (lambda this: String(this.python_string.upper())),
    [], types['Str'])

# Str.to_string
add_method(types['Str'], (lambda this: this), [], types['Str'])

# Int.to_string
add_method(types['Int'],
           (lambda this: String(str(this.python_int))), [], types['Str'])


class GenericType(Type):

    def __init__(self):
        super().__init__(OBJECT)


class GeneratorType(Type):

    def __init__(self, itemtype):
        super().__init__(OBJECT)
        self.itemtype = itemtype


# not all ModuleTypes are usable, only loaded ones are
#
# this is because modules are loaded when they are first imported, not when the
# bytecode file containing the module is loaded, that allows doing more magic
class ModuleType(Type):

    def __init__(self, compiled_path):
        super().__init__(OBJECT)
        self._attributes = None
        self.compiled_path = compiled_path

    # this is not really needed, it's just for debuggability
    def get_attribute(self, *args, **kwargs):
        assert self.loaded
        return super().get_attribute(*args, **kwargs)

    def load(self, exported_objects):
        self._attributes = [(False, objekt) for objekt in exported_objects]

    @property
    def loaded(self):
        return (self._attributes is not None)


class String(Object):

    def __init__(self, python_string):
        super().__init__(types['Str'])
        self.python_string = python_string

    def __repr__(self):
        return '<%s.%s: %r>' % (type(self).__module__, type(self).__name__,
                                self.python_string)


class Integer(Object):

    def __init__(self, python_int):
        super().__init__(types['Int'])
        assert isinstance(python_int, int)
        self.python_int = python_int

    def plus(self, other):
        return Integer(self.python_int + other.python_int)

    def minus(self, other):
        return Integer(self.python_int - other.python_int)

    def prefix_minus(self):
        return Integer(-self.python_int)

    def times(self, other):
        return Integer(self.python_int * other.python_int)

#    def divide(self, other):
#        return ???(self.python_int / other.python_int)

    def equal(self, other):
        return TRUE if self.python_int == other.python_int else FALSE


class Generator(Object):

    def __init__(self, tybe, next_callback):
        assert isinstance(tybe, GeneratorType)
        super().__init__(tybe)
        self.next = next_callback


TRUE = Object(types['Bool'])
FALSE = Object(types['Bool'])

T = GenericType()
BUILTINS = [
    # print
    Function(FunctionType([types['Str']], None),
             lambda arg: print(arg.python_string)),
    TRUE,
    FALSE,
    # next
    Function(FunctionType([GeneratorType(T)], T),
             lambda arg: arg.next()),
]
del T
