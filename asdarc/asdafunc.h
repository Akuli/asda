// functions objects for functions defined in asda

#ifndef ASDAFUNC_H
#define ASDAFUNC_H

#include "bc.h"
#include "interp.h"
#include "objtyp.h"

// TODO: returning functions

// bc is never destroyed because destroying the bc of the entire file will destroy it eventually
struct Object *asdafunc_create_noret(struct Interp *interp, struct Object *defscope, struct Bc bc);

#endif   // ASDAFUNC_H
