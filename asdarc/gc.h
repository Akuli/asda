#ifndef GC_H
#define GC_H

// I don't fully understand why compiling fails without this
#include "objtyp.h"    // IWYU pragma: keep

struct Interp;

void gc_refcountdebug(struct Interp *interp);

#endif   // GC_H
