#include "scope.h"
#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "../builtin.h"
#include "../interp.h"
#include "../objtyp.h"
#include "err.h"

static void destroy_scope(Object *obj, bool decrefrefs, bool freenonrefs)
{
	ScopeObject *scope = (ScopeObject *)obj;
	if (decrefrefs) {
		for (size_t i = 0; i < scope->nlocals; i++)
			if (scope->locals[i])
				OBJECT_DECREF(scope->locals[i]);

		if (scope->nparents != 0) OBJECT_DECREF(scope->parents[scope->nparents - 1]);
	}

	if (freenonrefs) {
		free(scope->locals);
		free(scope->parents);
	}
}

ScopeObject *scopeobj_newsub(Interp *interp, ScopeObject *parent, size_t nlocals)
{
	Object **locals;
	if (nlocals) {
		if (!( locals = calloc(nlocals, sizeof(locals[0])) )) {
			errobj_set_nomem(interp);
			return NULL;
		}
	} else
		locals = NULL;

	ScopeObject **parents;
	size_t nparents;
	if (parent) {
		nparents = parent->nparents + 1;
		if (!( parents = malloc(nparents * sizeof(parents[0])) )) {
			free(locals);
			errobj_set_nomem(interp);
			return NULL;
		}
	} else {
		parents = NULL;
		nparents = 0;
	}

	ScopeObject *obj = object_new(interp, &scopeobj_type, destroy_scope, sizeof(*obj));
	if (!obj) {
		free(parents);
		free(locals);
		return NULL;
	}

	if (parent) {
		memcpy(parents, parent->parents, parent->nparents * sizeof *parent->parents);
		parents[parent->nparents] = parent;
		OBJECT_INCREF(parent);
	}

	obj->locals = locals;
	obj->nlocals = nlocals;
	obj->parents = parents;
	obj->nparents = nparents;
	return obj;
}

ScopeObject *scopeobj_newglobal(Interp *interp)
{
	ScopeObject *res = scopeobj_newsub(interp, NULL, builtin_nobjects);
	if(!res)
		return NULL;

	memcpy(res->locals, builtin_objects, builtin_nobjects*sizeof(builtin_objects[0]));
	for (size_t i = 0; i < builtin_nobjects; i++)
		OBJECT_INCREF(res->locals[i]);
	return res;
}

ScopeObject *scopeobj_getforlevel(ScopeObject *scope, size_t level)
{
	assert(level <= scope->nparents);
	return (level == scope->nparents) ? scope : scope->parents[level];
}

const struct Type scopeobj_type = { .methods = NULL, .nmethods = 0 };
