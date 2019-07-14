// functions objects for functions defined in asda

#ifndef ASDAFUNC_H
#define ASDAFUNC_H

#include "code.h"
#include "interp.h"
#include "objects/func.h"
#include "objects/scope.h"

// code is never destroyed because destroying the code of the entire file will destroy it eventually
// this is used for both returning and non-returning asda functions
FuncObject *asdafunc_create(Interp *interp, ScopeObject *defscope, struct Code code);

#endif   // ASDAFUNC_H
