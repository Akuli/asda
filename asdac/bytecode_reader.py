import bisect
import collections
import functools
import io
import os

from . import common, decision_tree, objects, opcoder


class RecompileFixableError(Exception):
    """Raised for errors that can be fixed by recompiling a file.

    They happen when reading bytecode files, not when writing them.
    """

    def __init__(self, compilation, message):
        self.compilation = compilation
        self.message = message

    def __str__(self):
        return '%s (%r)' % (self.message, self.compilation)


# FIXME: this is HORRIBLY OUTDATED needs lot of updating
class _BytecodeReader:

    def __init__(self, compilation, file):
        self.compilation = compilation
        self.file = file

    def error(self, message):
        raise RecompileFixableError(self.compilation, message)

    # errors on unexpected eof
    def _read(self, size):
        result = self.file.read(size)
        if len(result) != size:
            self.error("the bytecode file seems to be truncated")
        return result

    def _read_uint(self, size):
        assert size % 8 == 0 and 0 < size <= 64, size
        return int.from_bytes(self._read(size // 8), 'little')

    read_uint8 = functools.partialmethod(_read_uint, 8)
    read_uint16 = functools.partialmethod(_read_uint, 16)
    read_uint32 = functools.partialmethod(_read_uint, 32)

    def read_string(self):
        length = self.read_uint32()
        utf8 = self._read(length)

        try:
            return utf8.decode('utf-8')
        except UnicodeDecodeError:
            bad = utf8.decode('utf-8', errors='replace')
            self.error("the file contains a string of invalid utf-8: " + bad)

    def read_path(self):
        relative_path = self.read_string().replace('/', os.sep)
        relative_to = self.compilation.compiled_path.parent
        assert relative_to.is_absolute()
        return common.resolve_dotdots(relative_to / relative_path)

    def read_type(self, *, name_hint='<unknown name>'):
        byte = self._read(1)

        if byte == TYPE_BUILTIN:
            index = self.read_uint8()
            return list(objects.BUILTIN_TYPES.values())[index]

        if byte == TYPE_FUNCTION:
            returntype = self.read_type()
            nargs = self.read_uint8()
            argtypes = [self.read_type() for junk in range(nargs)]
            return objects.FunctionType(argtypes, returntype)

        if byte == TYPE_GENERATOR:
            item_type = self.read_type()
            return objects.GeneratorType(item_type)

        if byte == TYPE_VOID:
            return None

        self.error("invalid type byte %r" % byte)

    def check_asda_part(self):
        if self.file.read(4) != b'asda':
            self.error("the file is not an asda bytecode file")

    def seek_to_end_sections(self):
        self.file.seek(-32//8, io.SEEK_END)
        new_seek_pos = self.read_uint32()
        self.file.seek(new_seek_pos)

    # returns a list of absolute source file paths
    # TODO: can this return compilation objects instead?
    def read_second_import_section(self):
        if self._read(1) != IMPORT_SECTION:
            self.error(
                "the file doesn't seem to have a valid second import section")

        result = []
        how_many = self.read_uint16()
        for junk in range(how_many):
            result.append(self.read_path())
        return result

    def read_export_section(self):
        if self._read(1) != EXPORT_SECTION:
            self.error("the file doesn't seem to have a valid export section")

        result = collections.OrderedDict()
        how_many = self.read_uint16()
        for junk in range(how_many):
            name = self.read_string()
            tybe = self.read_type(name_hint=name)
            result[name] = tybe
        return result


def read_imports_and_exports(compilation):
    with compilation.messager.indented(3, "Reading the compiled file..."):
        with compilation.compiled_path.open('rb') as file:
            reader = _BytecodeReader(compilation, file)
            reader.check_asda_part()
            reader.seek_to_end_sections()
            imports = reader.read_second_import_section()
            exports = reader.read_export_section()
            compilation.messager(4, "Imported files: " + (
                ', '.join(map(common.path_string, imports)) or '(none)'))

    return (imports, exports)
