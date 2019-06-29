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

struct Object *scopeobj_newglobal(struct Interp *interp);
struct Object *scopeobj_newsub(struct Interp *interp, struct Object *parent, uint16_t nlocals);

// does NOT return a new reference
struct Object *scopeobj_getforlevel(struct Object *scope, size_t level);

struct Object **scopeobj_getlocalvarsptr(struct Object *scope);

extern const struct Type scopeobj_type;

#endif   // OBJECTS_SCOPE_H
