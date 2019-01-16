"""Objects and other related things.

Even though types and generic functions are not objects in asda, they are
here as well.
"""

import abc
import collections

from asdac import common


class Type(metaclass=abc.ABCMeta):

    @property
    @abc.abstractmethod
    def name(self):
        """Returns a human-readable string, like "Generator[Str]"."""

    def undo_generics(self, type_dict):
        return self

    def __repr__(self):
        return '<cooked ast type %r>' % self.name


class BuiltinType(Type):

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name


BUILTIN_TYPES = collections.OrderedDict([
    ('Str', BuiltinType('Str')),
    ('Int', BuiltinType('Int')),
    ('Bool', BuiltinType('Bool')),
])


class FunctionType(Type):

    def __init__(self, name_prefix, argtypes=(), return_or_yield_type=None,
                 is_generator=False):
        self.argtypes = list(argtypes)
        self.return_or_yield_type = return_or_yield_type
        self.is_generator = is_generator
        self.name_prefix = name_prefix

    @property
    def name(self):
        return '%s(%s)' % (
            self.name_prefix,
            ', '.join(argtype.name for argtype in self.argtypes))

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented
        return (self.argtypes == other.argtypes and
                self.return_or_yield_type == other.return_or_yield_type and
                self.is_generator == other.is_generator)

    def undo_generics(self, type_dict, new_name_prefix=None):
        if new_name_prefix is None:
            new_name_prefix = self.name_prefix

        return FunctionType(
            new_name_prefix,
            [tybe.undo_generics(type_dict) for tybe in self.argtypes],
            self.return_or_yield_type.undo_generics(type_dict),
            self.is_generator)


class GeneratorType(Type):

    def __init__(self, item_type):
        self.item_type = item_type

    @property
    def name(self):
        return 'Generator[%s]' % self.item_type.name

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

    def __init__(self, name):
        self._name = name

    @property
    def name(self):
        return self._name

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
