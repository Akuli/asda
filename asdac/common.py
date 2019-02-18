import itertools


# these are for reading source files, as specified in docs/syntax.md
OPEN_KWARGS = {
    'encoding': 'utf-8-sig',    # like 'utf-8', but ignores a BOM
    # python accepts both LF and CRLF by default
}


class Location:

    def __init__(self, filename, offset, length):
        # these make debugging a lot easier, don't delete these
        assert isinstance(filename, str)
        assert offset >= 0
        assert length >= 0

        self.filename = filename
        self.offset = offset
        self.length = length

    def __repr__(self):
        return 'Location(%r, %r, %r)' % (
            self.filename, self.offset, self.length)

    def get_line_column_string(self):
        try:
            with open(self.filename, 'r', **OPEN_KWARGS) as file:
                before = file.read(self.offset)
                value = file.read(self.length)
            if len(before) != self.offset or len(value) != self.length:
                # this can happen when input e.g. comes from /dev/fd/something
                # but is hard to test
                raise OSError   # pragma: no cover
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
            self.filename, startline, startcolumn, endline, endcolumn)

    def __eq__(self, other):
        if not isinstance(other, Location):
            return NotImplemented
        return ((self.filename, self.offset, self.length) ==
                (other.filename, other.offset, other.length))

    # because operator magic is fun
    def __add__(self, other):
        if not isinstance(other, Location):
            return NotImplemented

        start = min(self.offset, other.offset)
        end = max(self.offset + self.length, other.offset + other.length)
        return Location(self.filename, start, end - start)

    def get_source(self):
        """Reads the code from the source file. Raises OSError on failure.

        This always reads and returns full lines of code, but the location may
        start or end in the middle of a line, so the lines are returned as a
        3-tuple of code before the location (but on *startline*), at the
        location and after the location (but on *endline*).

        A trailing newline is not included in the last part.
        """
        with open(self.filename, 'r', **OPEN_KWARGS) as file:
            before = file.read(self.offset)
            value = file.read(self.length)
            if len(before) != self.offset or len(value) != self.length:
                raise OSError("file ended sooner than expected")
            if value.endswith('\n'):
                after = ''
            else:
                after = file.readline().rstrip('\n')    # can become ''

        if before.endswith('\n'):
            before = ''
        else:
            before = before.rsplit('\n', 1)[-1]

        return (before, value, after)


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
