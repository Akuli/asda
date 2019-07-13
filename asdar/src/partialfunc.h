#ifndef PARTIALFUNC_H
#define PARTIALFUNC_H

#include <stddef.h>
#include "interp.h"
#include "objtyp.h"

struct FuncObject *
partialfunc_create(Interp *interp, struct FuncObject *f, struct Object *const *partial, size_t npartial);

#endif    // PARTIALFUNC_H
