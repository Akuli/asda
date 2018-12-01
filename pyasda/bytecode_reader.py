import functools

from . import objects


CREATE_FUNCTION = b'f'
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'
INT_CONSTANT = b'1'
CALL_FUNCTION = b'('
POP_ONE = b'P'


class _BytecodeReader:

    def __init__(self, read_callback):
        self._maybe_read = read_callback    # no error on eof, returns b''
        self.local_vars = []
        self.stack = []

    # errors on eof
    def _read(self, size):
        result = self._maybe_read(size)
        assert len(result) == size
        return result

    def _read_uint(self, size):
        assert size % 8 == 0 and 0 < size <= 64, size
        result = 0
        for offset in range(0, size, 8):
            result |= self._read(1)[0] << offset
        return result

    read_uint8 = functools.partialmethod(_read_uint, 8)
    read_uint16 = functools.partialmethod(_read_uint, 16)
    read_uint32 = functools.partialmethod(_read_uint, 32)
    read_uint64 = functools.partialmethod(_read_uint, 64)

    def read_string(self):
        length = self.read_uint32()
        utf8 = self._read(length)
        return utf8.decode('utf-8')

    # TODO: don't run the code right away for defining functions and stuff
    def read_body(self):
        how_many_vars = self.read_uint16()
        for junk in range(how_many_vars):
            self.read_string()      # the type
        self.local_vars[:] = [None] * how_many_vars

        while True:
            magic = self._maybe_read(1)
            if not magic:
                break

            if magic == STR_CONSTANT:
                self.stack.append(objects.AsdaString(self.read_string()))
            elif magic == CALL_FUNCTION:
                how_many_args = self.read_uint8()
                args = self.stack[-how_many_args:]
                del self.stack[-how_many_args:]
                func = self.stack.pop()
                self.stack.append(func.run(args))
            elif magic == LOOKUP_VAR:
                level = self.read_uint8()
                index = self.read_uint16()
                if level == 0:
                    self.stack.append(objects.BUILTINS[index])
                elif level == 1:
                    self.stack.append(self.local_vars[index])
                else:
                    assert False
            elif magic == SET_VAR:
                index = self.read_uint16()
                self.local_vars[index] = self.stack.pop()
            elif magic == POP_ONE:
                self.stack.pop()
            else:
                assert False, magic

        assert not self.stack


def read_bytecode(read_callback):
    asda = read_callback(4)
    if asda != b'asda':
        raise ValueError("doesn't look like a compiled asda file")

    reader = _BytecodeReader(read_callback)
    reader.read_body()

    if read_callback(1) != b'':
        raise ValueError("junk at the end of the compiled file")
