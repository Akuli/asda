import collections
import contextlib
import enum
import itertools
import os
import pathlib
import sys
import typing

from asdac import objects


# TODO: on windows, relpath doesn't work for things that are on a different
#       drive
def relpath(
        path: pathlib.Path,
        relative2: pathlib.Path = pathlib.Path('.')) -> pathlib.Path:
    """os.path.relpath for pathlib. Returns a pathlib.Path."""
    # needs str() because os.path doesn't like path objects on python 3.5
    return pathlib.Path(os.path.relpath(str(path), str(relative2)))


def path_string(path: pathlib.Path) -> str:
    """Converts a pathlib.Path to a human-readable string."""
    return str(relpath(path))


def resolve_dotdots(path: pathlib.Path) -> pathlib.Path:
    """Converts pathlib.Path('a/../b') to pathlib.Path('b')."""
    return pathlib.Path(os.path.normpath(str(path)))


class Messager:
    """Prints fancy messages to stderr.

    Unlike plain prints, this handles:
        * --verbose and --quiet arguments
        * prefixing every line with some string when wanted
        * indenting related messages so that it's easier to read them

    The "verbosity" is -1 if --quiet was used, and the number of times that
    --verbose was given otherwise (so usually it's zero).
    """

    def __init__(self, verbosity: int) -> None:
        self.verbosity = verbosity
        self.parent_messager: typing.Optional[Messager] = None
        self.prefix = ''

    # because magic is fun, returns whether something was printed
    def __call__(self, min_verbosity: int, string: str) -> bool:
        message = self.prefix + string
        if self.parent_messager is None:
            if self.verbosity >= min_verbosity:
                print(message, file=sys.stderr)
                return True
            return False

        return self.parent_messager(min_verbosity, message)

    @contextlib.contextmanager
    def indented(self,
            min_verbosity: int,
            string: str) -> typing.Iterator[None]:
        if not self(min_verbosity, string):
            yield
            return

        parentmost = self
        while parentmost.parent_messager is not None:
            parentmost = parentmost.parent_messager

        spaces = ' ' * 2
        parentmost.prefix = spaces + parentmost.prefix
        try:
            yield
        finally:
            assert parentmost.prefix.startswith(spaces)
            parentmost.prefix = parentmost.prefix[len(spaces):]

    def with_prefix(self, prefix: str) -> 'Messager':
        result = Messager(self.verbosity)
        result.parent_messager = self
        result.prefix = prefix + ': '
        return result


class Compilation:
    """Represents a source file and its corresponding bytecode file."""

    def __init__(self,
            source_path: pathlib.Path,
            compiled_dir: pathlib.Path,
            messager: Messager):
        self.messager = messager.with_prefix(path_string(source_path))
        self.source_path = source_path
        self.compiled_path = self._get_bytecode_path(compiled_dir)
        self.done = False

    def _get_bytecode_path(self, compiled_dir: pathlib.Path) -> pathlib.Path:
        relative = relpath(self.source_path, compiled_dir.parent)
        relative_c = relative.with_suffix('.asdac')

        # avoid having weird things happening
        # lowercasing makes the compiled files work on both case-sensitive and
        # case-insensitive file systems
        def handle_part(string: str) -> str:
            return 'dotdot' if string == '..' else string.lower()

        return compiled_dir / pathlib.Path(*map(handle_part, relative_c.parts))

    def __repr__(self) -> str:
        return '<%s of %s>' % (type(self).__name__, self.source_path)

    def open_source_file(self) -> typing.TextIO:
        # see docs/syntax.md
        # python accepts both LF and CRLF by default, but the default encoding
        # is platform-dependent (not utf8 on windows, lol)
        # utf-8-sig is like utf-8 but it ignores the bom, if there is a bom
        return self.source_path.open('r', encoding='utf-8-sig')

    def set_done(self) -> None:
        assert not self.done
        self.done = True


class Location:

    def __init__(
            self,
            compilation: Compilation,
            offset: int,
            length: int) -> None:
        # these make debugging a lot easier, don't delete these
        # but tests do magic
        if 'pytest' not in sys.modules:
            assert isinstance(compilation, Compilation)
        assert offset >= 0
        assert length >= 0

        self.compilation = compilation
        self.offset = offset
        self.length = length

    def __repr__(self) -> str:
        result = 'Location offset=%r length=%r' % (self.offset, self.length)
        try:
            result += ': ' + repr(self.get_source()[1])
        except OSError:
            pass
        except AttributeError:
            # tests do magic
            assert not isinstance(self.compilation, Compilation)
        return '<' + result + '>'

    # raises OSError
    def _read_before_value_after(self) -> typing.Tuple[str, str, str]:
        with self.compilation.open_source_file() as file:
            # seek won't do because seek wants a number of bytes, not number
            # of characters
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

    def get_line_column_string(self) -> str:
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
            path_string(self.compilation.source_path),
            startline, startcolumn, endline, endcolumn)

    def __eq__(self,
               other: typing.Any) -> typing.Union[bool, 'NotImplemented']:
        if not isinstance(other, Location):
            return NotImplemented
        return ((self.compilation, self.offset, self.length) ==
                (other.compilation, other.offset, other.length))

    # because operator magic is fun
    def __add__(self, other: 'Location') -> 'Location':
        if not isinstance(other, Location):
            return NotImplemented
        if self.compilation is not other.compilation:
            raise TypeError("cannot add locations of different compilations")

        start = min(self.offset, other.offset)
        end = max(self.offset + self.length, other.offset + other.length)
        return Location(self.compilation, start, end - start)

    def get_source(self) -> typing.Tuple[str, str, str]:
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

    # TODO: make the location non-optional?
    def __init__(
            self,
            message: str,
            location: typing.Optional[Location] = None):
        assert location is None or isinstance(location, Location)
        super().__init__(location, message)
        self.location = location
        self.message = message

    def __str__(self) -> str:
        return '%r: %s' % (self.location, self.message)
