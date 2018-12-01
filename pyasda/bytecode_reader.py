import functools

from . import objects


CREATE_FUNCTION = b'f'
LOOKUP_VAR = b'v'
SET_VAR = b'V'
STR_CONSTANT = b'"'
INT_CONSTANT = b'1'
CALL_FUNCTION = b'('


class _BytecodeReader:

    def __init__(self, read_callback):
        self._read_callback = read_callback
        self.local_vars = []

    def _read(self, size):
        result = self._read_callback(size)
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

        for junk in range(self.read_uint16()):
            magic = self._read(1)
            if magic == SET_VAR:
                index = self.read_uint16()
                self.local_vars[index] = self.read_expression()
            elif magic == CALL_FUNCTION:
                self.read_function_call()
            else:
                assert False, magic

    def read_function_call(self):
        func = self.read_expression()
        how_many_args = self.read_uint8()
        args = [self.read_expression() for junk in range(how_many_args)]
        return func.run(args)

    def read_expression(self):
        magic = self._read(1)
        if magic == STR_CONSTANT:
            return objects.AsdaString(self.read_string())
        elif magic == CALL_FUNCTION:
            return self.read_function_call()
        elif magic == LOOKUP_VAR:
            level = self.read_uint8()
            index = self.read_uint16()
            if level == 0:
                return objects.BUILTINS[index]
            if level == 1:
                return self.local_vars[index]
            assert False
        else:
            assert False, magic


def read_bytecode(read_callback):
    asda = read_callback(4)
    if asda != b'asda':
        raise ValueError("doesn't look like a compiled asda file")

    reader = _BytecodeReader(read_callback)
    reader.read_body()

    if read_callback(1) != b'':
        raise ValueError("junk at the end of the compiled file")
