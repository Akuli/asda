#ifndef PARTIALFUNC_H
#define PARTIALFUNC_H

#include <stddef.h>
#include "interp.h"
#include "objtyp.h"

Object *partialfunc_create(Interp *interp, Object *f, Object *const *partial, size_t npartial);

#endif    // PARTIALFUNC_H
