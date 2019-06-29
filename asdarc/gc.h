#ifndef GC_H
#define GC_H

#include "interp.h"

struct Interp;

void gc_refcountdebug(struct Interp *interp);

#endif   // GC_H
