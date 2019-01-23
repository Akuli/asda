"""Objects and other related things.

Even though types and generic functions are not objects in asda, they are
here as well.
"""

import abc
import collections
import itertools

from asdac import common


class Type(metaclass=abc.ABCMeta):

    def __init__(self, name, parent_type):
        self.name = name
        self.parent_type = parent_type      # None for OBJECT

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


OBJECT = Type('Object', None)


class FunctionType(Type):

    def __init__(self, name_prefix, argtypes=(), returntype=None, *,
                 is_method=False):
        self.argtypes = list(argtypes)

        argtype_names = [argtype.name for argtype in self.argtypes]
        if is_method:
            del argtype_names[0]

        super().__init__('%s(%s)' % (name_prefix, ', '.join(argtype_names)),
                         OBJECT)
        self.returntype = returntype
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

        # name_prefix is ignored on purpose
        return (self.argtypes == other.argtypes and
                self.returntype == other.returntype)

    def without_this_arg(self):
        assert self._is_method
        return FunctionType(
            self.name_prefix, self.argtypes[1:], self.returntype,
            is_method=False)

    def undo_generics(self, type_dict, new_name_prefix=None):
        if new_name_prefix is None:
            new_name_prefix = self.name_prefix

        return FunctionType(
            new_name_prefix,
            [tybe.undo_generics(type_dict) for tybe in self.argtypes],
            (None if self.returntype is None else
             self.returntype.undo_generics(type_dict)),
            is_method=self._is_method)


BUILTIN_TYPES = collections.OrderedDict([
    ('Str', Type('Str', OBJECT)),
    ('Int', Type('Int', OBJECT)),
    ('Bool', Type('Bool', OBJECT)),
    ('Object', OBJECT),
])
BUILTIN_TYPES['Str'].add_method('uppercase', [], BUILTIN_TYPES['Str'])


class GeneratorType(Type):

    def __init__(self, item_type):
        super().__init__('Generator[%s]' % item_type.name, OBJECT)
        self.item_type = item_type

    def __eq__(self, other):
        if not isinstance(other, GeneratorType):
            return NotImplemented
        return self.item_type == other.item_type

    def undo_generics(self, type_dict, new_name_prefix=None):
        return GeneratorType(self.item_type.undo_generics(type_dict))


BUILTIN_OBJECTS = collections.OrderedDict([
    ('print', FunctionType('print', [BUILTIN_TYPES['Str']])),
    ('TRUE', BUILTIN_TYPES['Bool']),
    ('FALSE', BUILTIN_TYPES['Bool']),
])


class GenericMarker(Type):

    def __init__(self, name):
        super().__init__(name, OBJECT)

    def undo_generics(self, type_dict):
        return type_dict.get(self, self)


# note: generics are NOT objects
#       generics are NOT types
#       generics are NOT functions
#       generics are something yet else :D
class Generic:

    # type_markers contains GenericMarker objects
    def __init__(self, type_markers, real_type):
        self.type_markers = type_markers
        self.real_type = real_type

    def get_real_type(self, the_types, error_location):
        if len(the_types) != len(self.type_markers):
            if len(self.type_markers) == 1:
                type_maybe_s = '1 type'
            else:
                type_maybe_s = '%d types' % len(self.type_markers)

            if hasattr(self.real_type, 'name_prefix'):
                name = '%s[%s]' % (
                    self.real_type.name_prefix,
                    ', '.join(marker.name for marker in self.type_markers))
            else:
                name = self.real_type.name

            raise common.CompileError(
                "%s expected %s, but got %d" % (
                    name, type_maybe_s, len(the_types)),
                error_location)

        type_dict = dict(zip(self.type_markers, the_types))
        if isinstance(self.real_type, FunctionType):
            new_name_prefix = '%s[%s]' % (
                self.real_type.name_prefix,
                ', '.join(tybe.name for tybe in the_types))
            return self.real_type.undo_generics(type_dict, new_name_prefix)

        return self.real_type.undo_generics(type_dict)


T = GenericMarker('T')
BUILTIN_GENERIC_FUNCS = collections.OrderedDict([
    ('next', Generic([T], FunctionType('next', [GeneratorType(T)], T))),
])
BUILTIN_GENERIC_TYPES = collections.OrderedDict([
    ('Generator', Generic([T], GeneratorType(T))),
])
del T
