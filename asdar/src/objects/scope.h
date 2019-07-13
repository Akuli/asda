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

extern const struct Type scopeobj_type;

struct ScopeObject {
	OBJECT_HEAD

	struct Object **locals;
	size_t nlocals;

	struct ScopeObject **parents;
	size_t nparents;
};

struct ScopeObject *scopeobj_newglobal(Interp *interp);
struct ScopeObject *scopeobj_newsub(Interp *interp, struct ScopeObject *parent, size_t nlocals);

// does NOT return a new reference
struct ScopeObject *scopeobj_getforlevel(struct ScopeObject *scope, size_t level);

// TODO: delete this and just access ->locals directly
struct Object **scopeobj_getlocalvarsptr(struct ScopeObject *scope);

#endif   // OBJECTS_SCOPE_H
