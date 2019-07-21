/*
Scopes are objects because functions have a definition scope and multiple
functions may have the same definition scope, and the definition scope has to
exist as long as the functions do. So scopes need ref counting. Objects already
implement a handy way to refcount, so that's used here.
*/

#ifndef OBJECTS_SCOPE_H
#define OBJECTS_SCOPE_H

#include <stddef.h>
#include "../interp.h"
#include "../object.h"

extern const struct Type scopeobj_type;

typedef struct ScopeObject {
	OBJECT_HEAD

	Object **locals;
	size_t nlocals;

	struct ScopeObject **parents;
	size_t nparents;
} ScopeObject;

ScopeObject *scopeobj_newglobal(Interp *interp);
ScopeObject *scopeobj_newsub(Interp *interp, ScopeObject *parent, size_t nlocals);

// does NOT return a new reference
ScopeObject *scopeobj_getforlevel(ScopeObject *scope, size_t level);

#endif   // OBJECTS_SCOPE_H
