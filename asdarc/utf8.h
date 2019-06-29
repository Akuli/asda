#ifndef UTF8_H
#define UTF8_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "interp.h"

// convert a Unicode string to a UTF-8 string
// after calling this, *utf8 is mallocced to utf8len+1 bytes, and last byte is 0
// there may be 0s in the first len bytes
// returns false on error
bool utf8_encode(Interp *interp, const uint32_t *unicode, size_t unicodelen, char **utf8, size_t *utf8len);

// convert a UTF-8 string to a Unicode string
// if utf8 is \0-terminated, pass strlen(utf8) for utf8len
// does NOT malloc and add a 0 byte to the end
// returns false on error
bool utf8_decode(Interp *interp, const char *utf8, size_t utf8len, uint32_t **unicode, size_t *unicodelen);

#endif   // UTF8_H
