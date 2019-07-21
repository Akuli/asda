#ifndef PARTIALFUNC_H
#define PARTIALFUNC_H

#include <stddef.h>
#include "interp.h"
#include "object.h"
#include "objects/func.h"

FuncObject *partialfunc_create(Interp *interp, FuncObject *f, Object *const *partial, size_t npartial);

#endif    // PARTIALFUNC_H
