#ifndef PARTIALFUNC_H
#define PARTIALFUNC_H

#include <stddef.h>
#include "interp.h"
#include "objtyp.h"
#include "objects/func.h"

struct Object *
partialfunc_create(struct Interp *interp, struct Object *f, struct Object *const *partial, size_t npartial);

#endif    // PARTIALFUNC_H
