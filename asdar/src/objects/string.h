#ifndef OBJECTS_STRING_H
#define OBJECTS_STRING_H

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "../interp.h"
#include "../object.h"


// TODO: switch to utf8 strings, and convert to unicode only when needed?

typedef struct StringObject {
	struct ObjectHead head;

	uint32_t *val;
	size_t len;

	// use stringobj_toutf8() instead of accessing these directly
	char *utf8cache;      // NULL if not cached yet, otherwise ends with '\0'
	size_t utf8cachelen;
} StringObject;

// this is kind of painful to use
// example:  struct StringObject hello = STRINGOBJ_COMPILETIMECREATE('h','e','l','l','o');
// only ascii supported
#define STRINGOBJ_COMPILETIMECREATE(...) { \
	.head = OBJECT_COMPILETIME_HEAD, \
	.val = (uint32_t[]){__VA_ARGS__}, \
	.len = sizeof( (uint32_t[]){__VA_ARGS__} ) / sizeof(uint32_t), \
	.utf8cache = (char[]){__VA_ARGS__, '\0'}, \
	.utf8cachelen = sizeof( (char[]){__VA_ARGS__} ), \
}

// creates a copy of the val and uses that
StringObject *stringobj_new(Interp *interp, const uint32_t *val, size_t len);

// the val will be freed (if error then immediately, otherwise whenever the object is destroyed)
StringObject *stringobj_new_nocpy(Interp *interp, uint32_t *val, size_t len);

// if your utf8 is 0 terminated, pass strlen(utf8) for utflen
StringObject *stringobj_new_utf8(Interp *interp, const char *utf, size_t utflen);

/*
printf-like string creating

format string must not come from user input:
- error handling may be assert() or missing
- constructing the string must not mean joining insanely many parts (see .c file for details)

here is spec:

	fmt part  argument type    description
	========  =============    ===========
	%s        const char *     \0 terminated utf-8 string
	%d        int              base 10
	%zu       size_t           base 10
	%S        StringObject *   string object
	%U        uint32_t         Unicode code point, e.g. "U+007A 'z'" for (uint32_t)'z'
	%B        unsigned char    byte with non-whitespace ascii character if any, e.g. "0x01" or "0x7a 'z'"
	%%        no argument      literal % character added to output
*/
StringObject *stringobj_new_format(Interp *interp, const char *fmt, ...);
StringObject *stringobj_new_vformat(Interp *interp, const char *fmt, va_list ap);

// behaves like utf8_encode.  DON'T FREE the val.
bool stringobj_toutf8(StringObject *obj, const char **val, size_t *len);

// checks if strings are equal
bool stringobj_eq(StringObject *a, StringObject *b);

// joins all da strings
StringObject *stringobj_join(Interp *interp, StringObject *const *strs, size_t nstrs);

#endif   // OBJECTS_STRING_H
