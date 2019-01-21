import itertools


class Location:

    def __init__(self, filename, startline, startcolumn, endline, endcolumn):
        # yes, comparing tuples works like this
        assert (startline, startcolumn) <= (endline, endcolumn)

        self.filename = filename
        self.startline = startline
        self.startcolumn = startcolumn
        self.endline = endline
        self.endcolumn = endcolumn

    def __str__(self):
        return '%s:%d,%d...%d,%d' % (
            self.filename, self.startline, self.startcolumn,
            self.endline, self.endcolumn)

    def __repr__(self):
        return 'Location(%r, %r, %r, %r, %r)' % (
            self.filename, self.startline, self.startcolumn,
            self.endline, self.endcolumn)

    def __eq__(self, other):
        if not isinstance(other, Location):
            return NotImplemented
        return ((self.filename, self.start, self.end) ==
                (other.filename, other.start, other.end))

    @property
    def start(self):
        return (self.startline, self.startcolumn)

    @property
    def end(self):
        return (self.endline, self.endcolumn)

    # because operator magic is fun
    def __add__(self, other):
        if not isinstance(other, Location):
            return NotImplemented

        assert self.filename == other.filename
        start = min(self.start, other.start)
        end = max(self.end, other.end)
        return Location(self.filename, *(start + end))

    def get_source(self):
        """Reads the code from the source file.

        This always reads and returns full lines of code, but the location may
        start or end in the middle of a line, so the lines are returned as a
        3-tuple of code before the location (but on *startline*), at the
        location and after the location (but on *endline*).

        A trailing newline is not included in the last part.
        """
        with open(self.filename, 'r') as file:
            # move to the first line, note that line numbers start at 1
            for lineno in range(1, self.startline):
                file.readline()

            # special case: only 1 line must be read
            if self.startline == self.endline:
                line = file.readline().rstrip('\n')
                return (line[:self.startcolumn],
                        line[self.startcolumn:self.endcolumn],
                        line[self.endcolumn:])

            first_line = file.readline().rstrip('\n')
            before_start = first_line[:self.startcolumn]
            lines = [first_line[self.startcolumn:]]

            lines.extend(
                file.readline().rstrip('\n')
                for lineno in range(self.startline+1, self.endline))

            last_line = file.readline().rstrip('\n')
            lines.append(last_line[:self.endcolumn])
            after_end = last_line[self.endcolumn:]

            return (before_start, '\n'.join(lines), after_end)


class CompileError(Exception):

    def __init__(self, message, location=None):
        assert location is None or isinstance(location, Location)
        super().__init__(location, message)
        self.location = location
        self.message = message

    def __str__(self):
        return str(self.location) + ': ' + self.message


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
