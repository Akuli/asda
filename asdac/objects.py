"""Objects and other related things.

Even though types and generic functions are not objects in asda, they are
here as well.
"""

import abc
import collections
import itertools

from asdac import common


class Type(metaclass=abc.ABCMeta):

    def __init__(self, name):
        self.name = name

        # keys are names, values are FunctionTypes with 'this' as first arg
        self.methods = collections.OrderedDict()

    def undo_generics(self, type_dict):
        return self

    def add_method(self, name, argtypes, *args, **kwargs):
        self.methods[name] = FunctionType(
            self.name + '.' + name, itertools.chain([self], argtypes),
            *args, is_method=True, **kwargs)

    def __repr__(self):
        return '<%s type %r>' % (__name__, self.name)


class BuiltinType(Type):
    pass


class FunctionType(Type):

    def __init__(self, name_prefix, argtypes=(), return_or_yield_type=None,
                 is_generator=False, *, is_method=False):
        self.argtypes = list(argtypes)

        argtype_names = [argtype.name for argtype in self.argtypes]
        if is_method:
            del argtype_names[0]

        super().__init__('%s(%s)' % (name_prefix, ', '.join(argtype_names)))
        self.return_or_yield_type = return_or_yield_type
        self.is_generator = is_generator
        self.name_prefix = name_prefix
        self._is_method = is_method

    def __repr__(self):
        result = super().__repr__()
        assert result[-1] == '>'
        if self._is_method:
            return result[:-1] + ', is a method>'
        return result

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented
        return (self.argtypes == other.argtypes and
                self.return_or_yield_type == other.return_or_yield_type and
                self.is_generator == other.is_generator)

    def without_this_arg(self):
        assert self._is_method
        return FunctionType(
            self.name_prefix, self.argtypes[1:], self.return_or_yield_type,
            self.is_generator, is_method=False)

    def undo_generics(self, type_dict, new_name_prefix=None):
        if new_name_prefix is None:
            new_name_prefix = self.name_prefix

        return FunctionType(
            new_name_prefix,
            [tybe.undo_generics(type_dict) for tybe in self.argtypes],
            self.return_or_yield_type.undo_generics(type_dict),
            self.is_generator)


BUILTIN_TYPES = collections.OrderedDict([
    ('Str', BuiltinType('Str')),
    ('Int', BuiltinType('Int')),
    ('Bool', BuiltinType('Bool')),
])
BUILTIN_TYPES['Str'].add_method('uppercase', [], BUILTIN_TYPES['Str'])


class GeneratorType(Type):

    def __init__(self, item_type):
        super().__init__('Generator[%s]' % item_type.name)
        self.item_type = item_type

    def __eq__(self, other):
        if not isinstance(other, GeneratorType):
            return NotImplemented
        return self.item_type == other.item_type

    def undo_generics(self, type_dict):
        return GeneratorType(self.item_type.undo_generics(type_dict))


BUILTIN_OBJECTS = collections.OrderedDict([
    ('print', FunctionType('print', [BUILTIN_TYPES['Str']])),
    ('TRUE', BUILTIN_TYPES['Bool']),
    ('FALSE', BUILTIN_TYPES['Bool']),
])


class GenericMarker(Type):

    def undo_generics(self, type_dict):
        return type_dict.get(self, self)


# note: generic functions are NOT objects
#       generic functions are NOT types
#       generic functions are something yet else :D
class GenericFunction:

    # type_markers contains GenericMarker objects
    # functype's name_prefix should be set properly
    def __init__(self, type_markers, functype):
        self.type_markers = type_markers
        self.functype = functype

    def get_function_type(self, the_types, error_location):
        if len(the_types) != len(self.type_markers):
            if len(self.type_markers) == 1:
                type_maybe_s = '1 type'
            else:
                type_maybe_s = '%d types' % len(self.type_markers)

            raise common.CompileError(
                "%s[...] expected %s, but got %d" % (
                    self.functype.name_prefix, type_maybe_s, len(the_types)),
                error_location)

        type_dict = dict(zip(self.type_markers, the_types))
        new_name_prefix = '%s[%s]' % (
            self.functype.name_prefix,
            ', '.join(tybe.name for tybe in the_types))
        return self.functype.undo_generics(type_dict, new_name_prefix)


T = GenericMarker('T')
BUILTIN_GENERIC_FUNCS = collections.OrderedDict([
    ('next', GenericFunction(
        [T], FunctionType('next', [GeneratorType(T)], T))),
])
del T
