#ifndef OBJECTS_INT_H
#define OBJECTS_INT_H

#include <stdbool.h>
#include <stddef.h>

#include <gmp.h>

#include "../interp.h"
#include "../object.h"
#include "string.h"

// not all IntObject pointers can be dereferenced, because pointer tagging magic

typedef struct IntObject {
	struct ObjectHead head;
	mpz_t mpz;
	StringObject *strobj;    // base 10, NULL for not cached yet
} IntObject;

// new integer from an arbitrarily long sequence of bytes (little-endian)
IntObject *intobj_new_lebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate);
IntObject *intobj_new_long(Interp *interp, long val);

// does the integer fit to a long?
bool intobj_fits2long(IntObject *x);

// returns the value as long, assuming it fits to long
long intobj_getlong(IntObject *x);

// similar to most other cmp-suffixed c functions
// returns 0 if a=b, negative if a<b, positive if a>b
int intobj_cmp(IntObject *x, IntObject *y);
int intobj_cmp_long(IntObject *x, long y);

IntObject *intobj_add(Interp *interp, IntObject *x, IntObject *y);  // x+y
IntObject *intobj_sub(Interp *interp, IntObject *x, IntObject *y);  // x-y
IntObject *intobj_neg(Interp *interp, IntObject *x);                // -x
IntObject *intobj_mul(Interp *interp, IntObject *x, IntObject *y);  // x*y

/*
Usage:

	char tmp[INTOBJ_TOCSTR_TMPSZ];
	const char *str = intobj_tocstr(interp, intobj, tmp);
	if (!str)
		// error

	// do something with str, but DON'T do anything with tmp
*/
#define INTOBJ_TOCSTR_TMPSZ 100
const char *intobj_tocstr(Interp *interp, IntObject *x, char *tmp);

// may fail, otherwise returns a new reference
StringObject *intobj_tostrobj(Interp *interp, IntObject *x);

// for cfunc_addmany
extern const struct CFunc intobj_cfuncs[];

#endif   // OBJECTS_INT_H
