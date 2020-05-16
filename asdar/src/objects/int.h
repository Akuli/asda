#ifndef OBJECTS_INT_H
#define OBJECTS_INT_H

#include <stdbool.h>
#include <stddef.h>

#include <gmp.h>

#include "../interp.h"
#include "../object.h"
#include "string.h"


typedef struct IntObject {
	struct ObjectHead head;

	// don't use any of this stuff outside int.c

	/** Represents if the Int has "spilled", i.e. > LONG_MAX || LONG_MIN */
	bool spilled;

	union {
		long lon;   // spilled==false
		mpz_t mpz;  // spilled==true
	} val;

	// TODO: add a function that computes and returns this when needed
	StringObject *str;   // string object, in base 10, NULL for not computed yet
} IntObject;

// returns a new integer from an arbitrarily long sequence of bytes (little-endian)
IntObject *intobj_new_lebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate);

IntObject *intobj_new_long(Interp *interp, long l);

// similar to most other cmp-suffixed c functions
// returns 0 if a=b, negative if a<b, positive if a>b
int intobj_cmp(IntObject *x, IntObject *y);
int intobj_cmp_long(IntObject *x, long y);

IntObject *intobj_add(Interp *interp, IntObject *x, IntObject *y);  // x+y
IntObject *intobj_sub(Interp *interp, IntObject *x, IntObject *y);  // x-y
IntObject *intobj_neg(Interp *interp, IntObject *x);                       // -x
IntObject *intobj_mul(Interp *interp, IntObject *x, IntObject *y);  // x*y

// use this instead of accessing x->str directly, because x->str may be NULL
// returns NULL on error
StringObject *intobj_tostrobj(Interp *interp, IntObject *x);

// returns NULL on error, return value is \0 terminated and must NOT be free()d
const char *intobj_tocstr(Interp *interp, IntObject *x);

// for cfunc_addmany
extern const struct CFunc intobj_cfuncs[];

#endif   // OBJECTS_INT_H
