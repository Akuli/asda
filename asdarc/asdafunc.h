// functions objects for functions defined in asda

#ifndef ASDAFUNC_H
#define ASDAFUNC_H

#include <stdbool.h>
#include "code.h"
#include "interp.h"
#include "objtyp.h"

// bc is never destroyed because destroying the bc of the entire file will destroy it eventually
// ret==true means returns a value, false means returns void or doesnt return
Object *asdafunc_create(Interp *interp, Object *defscope, struct Code code, bool ret);

#endif   // ASDAFUNC_H
