/*
Scopes are objects because functions have a definition scope and multiple
functions may have the same definition scope, and the definition scope has to
exist as long as the functions do. So scopes need ref counting. Objects already
implement a handy way to refcount, so that's used here.
*/

#ifndef OBJECTS_SCOPE_H
#define OBJECTS_SCOPE_H

#include <stddef.h>
#include <stdint.h>
#include "../interp.h"
#include "../objtyp.h"

Object *scopeobj_newglobal(Interp *interp);
Object *scopeobj_newsub(Interp *interp, Object *parent, uint16_t nlocals);

// does NOT return a new reference
Object *scopeobj_getforlevel(Object *scope, size_t level);

Object **scopeobj_getlocalvarsptr(Object *scope);

extern const struct Type scopeobj_type;

#endif   // OBJECTS_SCOPE_H
