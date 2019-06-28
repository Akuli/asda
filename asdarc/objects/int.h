#ifndef OBJECTS_INT_H
#define OBJECTS_INT_H

#include <gmp.h>
#include "../interp.h"

// returns a new integer from an arbitrarily long sequence of bytes (big-endian)
struct Object *intobj_new_bebytes(struct Interp *interp, const unsigned char *seq, size_t len, bool negate);

struct Object *intobj_add(struct Interp *interp, struct Object *x, struct Object *y);  // x+y
struct Object *intobj_sub(struct Interp *interp, struct Object *x, struct Object *y);  // x-y
struct Object *intobj_neg(struct Interp *interp, struct Object *x);                    // -x
struct Object *intobj_mul(struct Interp *interp, struct Object *x, struct Object *y);  // x*y


extern const struct Type intobj_type;

#endif   // OBJECTS_INT_H
