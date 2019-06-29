// functions objects for functions defined in asda

#ifndef ASDAFUNC_H
#define ASDAFUNC_H

#include <stdbool.h>
#include "bc.h"
#include "interp.h"
#include "objtyp.h"

// bc is never destroyed because destroying the bc of the entire file will destroy it eventually
// ret==true means returns a value, false means returns void or doesnt return
struct Object *asdafunc_create(struct Interp *interp, struct Object *defscope, struct Bc bc, bool ret);

#endif   // ASDAFUNC_H
