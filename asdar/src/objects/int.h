#ifndef OBJECTS_INT_H
#define OBJECTS_INT_H

#include <stdbool.h>
#include <stddef.h>
#include "../interp.h"
#include "../objtyp.h"

// returns a new integer from an arbitrarily long sequence of bytes (big-endian)
Object *intobj_new_bebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate);

Object *intobj_new_long(Interp *interp, long l);

// similar to most other cmp-suffixed c functions
// returns 0 if a=b, negative if a<b, positive if a>b
int intobj_cmp(Object *x, Object *y);
int intobj_cmp_long(Object *x, long y);

Object *intobj_add(Interp *interp, Object *x, Object *y);  // x+y
Object *intobj_sub(Interp *interp, Object *x, Object *y);  // x-y
Object *intobj_neg(Interp *interp, Object *x);             // -x
Object *intobj_mul(Interp *interp, Object *x, Object *y);  // x*y

// returns NULL on error, return value is \0 terminated and must NOT be free()d
const char *intobj_tocstr(Interp *interp, Object *x);

extern const struct Type intobj_type;

#endif   // OBJECTS_INT_H
