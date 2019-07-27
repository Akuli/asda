"""Objects and other related things.

Even though types, generic types and generic variables are not objects in asda,
they are here as well.
"""

import collections

from asdac import common


class Type:

    def __init__(self, name, parent_type):
        self.name = name
        self.parent_type = parent_type      # OBJECT's parent_type is None

        # the following things don't work well with inheritance
        # for now, create the subclasses in a for loop
        #
        # refactoring note: collections.ChainMap can't be used for ordered
        # things, because its source code has this:
        #
        #    def __iter__(self):
        #        return iter(set().union(*self.maps))

        # keys are strings, values are types
        self.attributes = collections.OrderedDict()

        # you can set this to a list of types
        self.constructor_argtypes = None

    def undo_generics(self, type_dict):
        return self

    def add_method(self, name, argtypes, returntype):
        self.attributes[name] = FunctionType(argtypes, returntype)

    def __repr__(self):
        return '<%s type %r>' % (__name__, self.name)


class FunctionType(Type):

    # returntype can be None for void return
    def __init__(self, argtypes, returntype):
        self.argtypes = list(argtypes)

        super().__init__(
            'functype{(%s) -> %s}' % (
                ', '.join(argtype.name for argtype in self.argtypes),
                'void' if returntype is None else returntype.name,
            ), BUILTIN_TYPES['Object'])
        self.returntype = returntype

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented

        return (self.argtypes == other.argtypes and
                self.returntype == other.returntype)

    def undo_generics(self, type_dict):
        return FunctionType(
            [tybe.undo_generics(type_dict) for tybe in self.argtypes],
            (None if self.returntype is None else
             self.returntype.undo_generics(type_dict)))


def _fill_builtin_types_ordered_dict():
    def create_and_add(name, baseclass):
        BUILTIN_TYPES[name] = Type(name, baseclass)

    objekt = Type('Object', None)
    create_and_add('Str', objekt)
    create_and_add('Int', objekt)
    create_and_add('Bool', objekt)
    BUILTIN_TYPES['Object'] = objekt

    # Object is needed for creating functions, and that is needed for adding
    # methods
    BUILTIN_TYPES['Str'].add_method('uppercase', [], BUILTIN_TYPES['Str'])
    BUILTIN_TYPES['Str'].add_method('lowercase', [], BUILTIN_TYPES['Str'])
    BUILTIN_TYPES['Str'].add_method('to_string', [], BUILTIN_TYPES['Str'])
    BUILTIN_TYPES['Int'].add_method('to_string', [], BUILTIN_TYPES['Str'])

    create_and_add('Error', objekt)
    for name in ['NoMemError', 'VariableError', 'ValueError', 'OsError']:
        create_and_add(name, BUILTIN_TYPES['Error'])
        BUILTIN_TYPES[name].add_method('to_string', [], BUILTIN_TYPES['Str'])

        # TODO: OsError should take errno as constructor argument
        #       or on windows, whatever it has instead of errno
        if name != 'NoMemError':
            BUILTIN_TYPES[name].constructor_argtypes = [BUILTIN_TYPES['Str']]


BUILTIN_TYPES = collections.OrderedDict()
_fill_builtin_types_ordered_dict()

BUILTIN_VARS = collections.OrderedDict([
    ('print', FunctionType([BUILTIN_TYPES['Str']], None)),
    ('TRUE', BUILTIN_TYPES['Bool']),
    ('FALSE', BUILTIN_TYPES['Bool']),
])


class GeneratorType(Type):

    def __init__(self, item_type):
        super().__init__('Generator[%s]' % item_type.name,
                         BUILTIN_TYPES['Object'])
        self.item_type = item_type

    def __eq__(self, other):
        if not isinstance(other, GeneratorType):
            return NotImplemented
        return self.item_type == other.item_type

    def undo_generics(self, type_dict):
        return GeneratorType(self.item_type.undo_generics(type_dict))


class GenericMarker(Type):

    def __init__(self, name):
        super().__init__(name, BUILTIN_TYPES['Object'])

    def undo_generics(self, type_dict):
        return type_dict.get(self, self)


# note: generics are NOT objects
#       generics are NOT types
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

            raise common.CompileError(
                "expected %s, [%s], but got %d" % (
                    type_maybe_s,
                    ', '.join(tm.name for tm in self.type_markers),
                    len(the_types)),
                error_location)

        type_dict = dict(zip(self.type_markers, the_types))
        return self.real_type.undo_generics(type_dict)


T = GenericMarker('T')
BUILTIN_GENERIC_TYPES = collections.OrderedDict([
    ('Generator', Generic([T], GeneratorType(T))),
])
BUILTIN_GENERIC_VARS = collections.OrderedDict([
    ('next', Generic([T], FunctionType([GeneratorType(T)], T))),
])
del T
