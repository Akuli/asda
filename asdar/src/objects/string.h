#ifndef OBJECTS_STRING_H
#define OBJECTS_STRING_H

#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "../cfunc.h"
#include "../interp.h"
#include "../object.h"

typedef struct {
	struct ObjectHead head;
	size_t utf8len;

	// utf8 is always '\0' terminated, but may contain other '\0' bytes too
	// ct = compile time, rt = run time
	const char *utf8ct;  // content of the string for CT strings, NULL for RT strings
	char utf8rt[];       // not used for CT strings because there's no way to initialize this at CT
} StringObject;

// s must be a string literal and valid utf-8
#define STRINGOBJ_COMPILETIMECREATE(s) { \
	.head = OBJECT_COMPILETIME_HEAD, \
	.utf8len = sizeof(s) - 1, \
	.utf8ct = s, \
}

// string creation functions try to make sure that this the only empty string
extern StringObject stringobj_empty;

// never fails
const char *stringobj_getutf8(StringObject *s);

/*
Creates a copy of the utf8 and uses that.

The utf8 doesn't need to be '\0' terminated. Make sure that you are not passing in
invalid utf8 (use utf8_validate with user inputs).

If utf8 is NULL, then the content is left uninitialized. After a succesful call

	StringObject *str = stringobject_new(interp, NULL, n);

you must immediately fill the first n bytes of str->utf8rt. The n'th byte is
already to set to '\0' for you, so don't overwrite that. This is the most efficient
way to create a string, because it doesn't involve reallocing or memmoving. The
downside is that you need to know beforehand how long the string will be. Use
stringobj_new_nocp() if you already have a malloc()ed char* string.
*/
StringObject *stringobj_new(Interp *interp, const char *utf8, size_t utf8len);

// Create a string from a malloc()ed char* utf8 string
StringObject *stringobj_new_nocp(Interp *interp, char *utf8, size_t utf8len);

/*
printf-like string creating

format string must not come from user input, because error handling may be assert() or missing

here is spec:

	fmt part  argument type    description
	========  =============    ===========
	%s        const char *     \0 terminated utf-8 string (it gets validated)
	%d        int              base 10
	%zu       size_t           base 10
	%S        StringObject *   string object
	%U        uint32_t         Unicode codepoint (possibly invalid), e.g. "U+007a 'z'" for (uint32_t)'z'
	%B        unsigned char    byte with non-whitespace ascii character if any, e.g. "0x01" or "0x7a 'z'"
	%%        no argument      literal % character added to output
*/
StringObject *stringobj_new_format(Interp *interp, const char *fmt, ...);
StringObject *stringobj_new_vformat(Interp *interp, const char *fmt, va_list ap);

// checks if strings are equal, never fails
bool stringobj_eq(StringObject *a, StringObject *b);

// joins all da strings
StringObject *stringobj_join(Interp *interp, StringObject *const *strs, size_t nstrs);

// methods and '+' operator, for cfunc_addmany()
extern const struct CFunc stringobj_cfuncs[];

#endif   // OBJECTS_STRING_H
