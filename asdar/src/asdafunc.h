// functions objects for functions defined in asda

#ifndef ASDAFUNC_H
#define ASDAFUNC_H

#include <stdbool.h>
#include "code.h"
#include "interp.h"
#include "objtyp.h"

// code is never destroyed because destroying the code of the entire file will destroy it eventually
// this is used for both returning and non-returning asda functions
Object *asdafunc_create(Interp *interp, Object *defscope, struct Code code);

#endif   // ASDAFUNC_H
