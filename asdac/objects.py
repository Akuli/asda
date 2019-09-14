"""Objects and other related things.

Even though types, generic types and generic variables are not objects in asda,
they are here as well.
"""

import collections
import copy

from asdac import common


# non-settable attributes are aka read-only
Attribute = collections.namedtuple('Attribute', ['tybe', 'settable'])

GenericInfo = collections.namedtuple('GenericInfo', ['generic_obj', 'types'])


class Type:

    # if you want the name to change when the class is mutated, you can pass
    # None for __init__'s name and override the name property
    def __init__(self, name, parent_type):
        self._name = name
        self.parent_type = parent_type      # OBJECT's parent_type is None
        self.generic_types = []             # for doing ThisType[blah blah]

        # the following things don't work well with inheritance
        # see creation of Error and its subclasses for a workaround
        #
        # refactoring note: collections.ChainMap can't be used for ordered
        # things, because its source code has this:
        #
        #    def __iter__(self):
        #        return iter(set().union(*self.maps))

        # keys are strings, values are Attribute namdtuples
        self.attributes = collections.OrderedDict()

        # you can set this to a list of types
        self.constructor_argtypes = None

        # this attribute is how to get Array[T] from Array[Str]
        # turning Array[T] to Array[Str] is called substituting
        self.original_generic = None

        # to prevent recursion
        # for example, Str has a method that returns Str
        # so Str's undo_generics_may_do_something must be False
        # remember to set this to True if you change .generic_types
        self.undo_generics_may_do_something = False

    def __eq__(self, other):
        if not isinstance(other, Type):
            return NotImplemented

        if self.generic_types:
            return (self.generic_types == other.generic_types and
                    self.original_generic == other.original_generic)
        return (self is other)

    def __hash__(self):
        if self.generic_types:
            return hash(tuple(self.generic_types) + (self.original_generic,))
        return super().__hash__()

    @property
    def name(self):
        if self.generic_types:
            return '%s[%s]' % (self._name, ', '.join(
                tybe.name for tybe in self.generic_types))
        return self._name

    # override _undo_generics_internal instead of overriding this
    # always returns a copy
    def undo_generics(self, type_dict):
        if not self.undo_generics_may_do_something:
            return self

        result = self._undo_generics_internal(type_dict)
        if self.generic_types and result.original_generic is None:
            assert result is not self
            result.original_generic = self
        return result

    def _undo_generics_internal(self, type_dict):
        result = copy.copy(self)
        result.attributes = collections.OrderedDict(
            (name, attr._replace(tybe=attr.tybe.undo_generics(type_dict)))
            for name, attr in self.attributes.items()
        )
        if self.constructor_argtypes is not None:
            result.constructor_argtypes = [
                tybe.undo_generics(type_dict)
                for tybe in self.constructor_argtypes
            ]
        result.generic_types = [
            tybe.undo_generics(type_dict)
            for tybe in self.generic_types
        ]
        return result

    def add_method(self, name, argtypes, returntype):
        self.attributes[name] = Attribute(
            FunctionType(argtypes, returntype), False)

    def __repr__(self):
        return '<%s type %r>' % (__name__, self.name)


class FunctionType(Type):

    # returntype can be None for void return
    def __init__(self, argtypes, returntype):
        self.argtypes = list(argtypes)

        super().__init__(None, BUILTIN_TYPES['Object'])
        self.returntype = returntype
        self.undo_generics_may_do_something = True

    @property
    def name(self):
        return 'functype{(%s) -> %s}' % (
            ', '.join(argtype.name for argtype in self.argtypes),
            'void' if self.returntype is None else self.returntype.name,
        )

    def __eq__(self, other):
        if not isinstance(other, FunctionType):
            return NotImplemented

        return (self.argtypes == other.argtypes and
                self.returntype == other.returntype)

    def _undo_generics_internal(self, type_dict):
        result = super()._undo_generics_internal(type_dict)
        result.argtypes = [tybe.undo_generics(type_dict)
                           for tybe in self.argtypes]
        if result.returntype is not None:
            result.returntype = result.returntype.undo_generics(type_dict)
        return result

    def remove_this_arg(self, this_arg_type):
        assert self.argtypes[0] == this_arg_type
        return FunctionType(self.argtypes[1:], self.returntype)


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
    BUILTIN_TYPES['Str'].add_method('get_length', [], BUILTIN_TYPES['Int'])
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


# feels nice and evil to create a class with just one method >xD MUHAHAHA ...
class UserDefinedClass(Type):

    def __init__(self, name, attr_arg_types: collections.OrderedDict):
        super().__init__(name, BUILTIN_TYPES['Object'])

        assert not self.attributes
        self.attributes.update(
            (name, Attribute(tybe, True))
            for name, tybe in attr_arg_types.items()
        )
        # self.attributes will also contain methods added with add_method()

        self.undo_generics_may_do_something = True
        self.constructor_argtypes = list(attr_arg_types.values())


class GenericMarker(Type):

    def __init__(self, name):
        super().__init__(name, BUILTIN_TYPES['Object'])
        self.undo_generics_may_do_something = True

    def _undo_generics_internal(self, type_dict):
        return type_dict.get(self, self)


def n_types(n):
    if n == 1:
        return '1 type'
    return '%d types' % n


# turns Array[T] into Array[Str], for example
def substitute_generics(tybe, markers, types_to_substitute, error_location):
    assert markers
    if len(types_to_substitute) != len(markers):
        raise common.CompileError(
            "needs %s, but got %s: [%s]"
            % (n_types(len(markers)),
               n_types(len(types_to_substitute)),
               ', '.join(t.name for t in types_to_substitute)),
            error_location)

    mapping = dict(zip(markers, types_to_substitute))
    return tybe.undo_generics(mapping)


T = GenericMarker('T')

array = Type('Array', BUILTIN_TYPES['Object'])
array.generic_types.append(T)
array.undo_generics_may_do_something = True
array.constructor_argtypes = []
array.add_method('get_length', [], BUILTIN_TYPES['Int'])
array.add_method('push', [T], None)
array.add_method('pop', [], T)
array.add_method('get', [BUILTIN_TYPES['Int']], T)

BUILTIN_GENERIC_TYPES = collections.OrderedDict([
    ('Array', array),
])

# TODO: handle built-in generic vars in rest of asdac
BUILTIN_GENERIC_VARS = collections.OrderedDict([
    # TODO: delete this, it's here only because tests use it and not actually
    # implemented anywhere
    ('next', (FunctionType([BUILTIN_GENERIC_TYPES['Array']], T), [T])),
])

del T
