#ifndef OBJECTS_INT_H
#define OBJECTS_INT_H

#include <gmp.h>
#include "../interp.h"

// will clear the mpz_t (immediately on error, otherise when returned object is destroyed)
struct Object *intobj_new_mpzt(struct Interp *interp, mpz_t mpz);

// returns a new integer from an arbitrarily long sequence of bytes (big-endian)
struct Object *intobj_new_bebytes(struct Interp *interp, const unsigned char *seq, size_t len, bool negate);


extern const struct Type intobj_type;

#endif   // OBJECTS_INT_H
