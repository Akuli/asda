import collections
import enum
import itertools
import os


class CompilationState(enum.Enum):
    NOTHING_DONE = 0
    IMPORTS_KNOWN = 1
    EXPORTS_KNOWN = 2
    DONE = 3


class Compilation:
    """Represents a source file and its corresponding bytecode file."""

    def __init__(self, source_path, compiled_dir):
        self.source_path = source_path
        self.compiled_path = self._get_bytecode_path(compiled_dir)

        self.state = CompilationState.NOTHING_DONE
        self.imports = None     # list of other Compilation objects
        self.exports = None     # ordered dict like {name: type}

    def _get_bytecode_path(self, compiled_dir):
        relative = os.path.relpath(self.source_path,
                                   os.path.dirname(compiled_dir))
        relative += 'c'     # lel.asda --> lel.asdac

        # avoid having weird things happening
        def handle_dotdot(string):
            return 'dotdot' if string == '..' else string

        relative = os.sep.join(map(handle_dotdot, relative.split(os.sep)))

        return os.path.join(compiled_dir, relative)

    def __repr__(self):
        return '<%s of %s>' % (type(self).__name__, self.source_path)

    def open_source_file(self):
        # see docs/syntax.md
        # python accepts both LF and CRLF by default, but the default encoding
        # is platform-dependent (not utf8 on windows, lol)
        # utf-8-sig is like utf-8 but it ignores the bom, if there is a bom
        return open(self.source_path, 'r', encoding='utf-8-sig')

    def set_imports(self, import_compilations):
        assert self.state == CompilationState.NOTHING_DONE
        assert isinstance(import_compilations, list)
        self.state = CompilationState.IMPORTS_KNOWN
        self.imports = import_compilations

    def set_exports(self, exports):
        assert self.state == CompilationState.IMPORTS_KNOWN
        assert isinstance(exports, collections.OrderedDict)
        self.state = CompilationState.DONE
        self.exports = exports

    def set_done(self):
        assert self.state == CompilationState.EXPORTS_KNOWN
        self.state = CompilationState.DONE


class Location:

    def __init__(self, compilation, offset, length):
        # these make debugging a lot easier, don't delete these
        assert isinstance(compilation, Compilation)
        assert offset >= 0
        assert length >= 0

        self.compilation = compilation
        self.offset = offset
        self.length = length

    def __repr__(self):
        return 'Location(%r, %r, %r)' % (
            self.compilation, self.offset, self.length)

    # raises OSError
    def _read_before_value_after(self):
        with self.compilation.open_source_file() as file:
            before = file.read(self.offset)
            value = file.read(self.length)

            # after is from this location to next \n (included)
            if value.endswith('\n'):
                after = ''
            else:
                after = file.readline()

        if len(before) != self.offset or len(value) != self.length:
            # this can happen when input e.g. comes from /dev/fd/something
            # but is hard to test
            raise OSError("file ended too soon")   # pragma: no cover

        return (before, value, after)

    def get_line_column_string(self):
        try:
            before, value, junk = self._read_before_value_after()
        except OSError:
            # not perfect, but is the best we can do
            startline = 1
            startcolumn = self.offset
            endline = 1
            endcolumn = self.offset + self.length
        else:
            startline = 1 + before.count('\n')
            startcolumn = len(before.rsplit('\n', 1)[-1])
            endline = startline + value.count('\n')
            endcolumn = len((before + value).rsplit('\n', 1)[-1])

        return '%s:%s,%s...%s,%s' % (
            self.compilation.source_path,
            startline, startcolumn, endline, endcolumn)

    def __eq__(self, other):
        if not isinstance(other, Location):
            return NotImplemented
        return ((self.compilation, self.offset, self.length) ==
                (other.compilation, other.offset, other.length))

    # because operator magic is fun
    def __add__(self, other):
        if not isinstance(other, Location):
            return NotImplemented
        if self.compilation is not other.compilation:
            raise TypeError("cannot add locations of different compilations")

        start = min(self.offset, other.offset)
        end = max(self.offset + self.length, other.offset + other.length)
        return Location(self.compilation, start, end - start)

    def get_source(self):
        """Reads the code from the source file. Raises OSError on failure.

        This always reads and returns full lines of code, but the location may
        start or end in the middle of a line, so the lines are returned as a
        3-tuple of code before the location, at the location and after the
        location.

        A trailing newline is not included in the last part.
        """
        before, value, after = self._read_before_value_after()
        return (before.rsplit('\n', 1)[-1], value, after.rstrip('\n'))


class CompileError(Exception):

    def __init__(self, message, location=None):
        assert location is None or isinstance(location, Location)
        super().__init__(location, message)
        self.location = location
        self.message = message

    def __str__(self):
        return '%r: %s' % (self.location, self.message)


# inheriting from this is a more debuggable alternative to "class Asd: pass"
class Marker:

    def __init__(self):
        # needs __dict__ because that way attributes don't inherit from
        # parent classes
        try:
            counts = type(self).__dict__['_counts']
        except KeyError:
            counts = type(self)._counts = itertools.count(1)
        self._count = next(counts)

    def __repr__(self):
        return '<%s %d>' % (type(self).__name__, self._count)
