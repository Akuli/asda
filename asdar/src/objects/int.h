#ifndef OBJECTS_INT_H
#define OBJECTS_INT_H

#include <stdbool.h>
#include <stddef.h>

#include <gmp.h>

#include "../interp.h"
#include "../objtyp.h"

extern const struct Type intobj_type;

struct IntObject {
	OBJECT_HEAD

	// don't use any of this stuff outside int.c

	/** Represents if the Int has "spilled", i.e. > LONG_MAX || LONG_MIN */
	bool spilled;

	union {
		long lon;   // spilled==false
		mpz_t mpz;  // spilled==true
	} val;

	// TODO: add a function that computes and returns this when needed
	struct StringObject *str;   // string object, in base 10, NULL for not computed yet
};

// returns a new integer from an arbitrarily long sequence of bytes (big-endian)
struct IntObject *intobj_new_bebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate);

struct IntObject *intobj_new_long(Interp *interp, long l);

// similar to most other cmp-suffixed c functions
// returns 0 if a=b, negative if a<b, positive if a>b
int intobj_cmp(struct IntObject *x, struct IntObject *y);
int intobj_cmp_long(struct IntObject *x, long y);

struct IntObject *intobj_add(Interp *interp, struct IntObject *x, struct IntObject *y);  // x+y
struct IntObject *intobj_sub(Interp *interp, struct IntObject *x, struct IntObject *y);  // x-y
struct IntObject *intobj_neg(Interp *interp, struct IntObject *x);                       // -x
struct IntObject *intobj_mul(Interp *interp, struct IntObject *x, struct IntObject *y);  // x*y

// returns NULL on error, return value is \0 terminated and must NOT be free()d
const char *intobj_tocstr(Interp *interp, struct IntObject *x);

#endif   // OBJECTS_INT_H
