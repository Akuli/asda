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

struct ScopeData {
	Object **locals;
	size_t nlocals;

	/* XXX: do we need to manage references to parents? */
	size_t nparents;
	Object **parents;
};

static void scopedata_destroy_without_pointer(struct ScopeData data, bool decrefrefs, bool freenonrefs)
{
	if (decrefrefs) {
		for (size_t i = 0; i < data.nlocals; i++)
			if (data.locals[i])
				OBJECT_DECREF(data.locals[i]);

		if (data.nparents != 0) OBJECT_DECREF(data.parents[data.nparents - 1]);
	}
	if (freenonrefs)
		free(data.locals);

	free(data.parents);
}

static void scopedata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	scopedata_destroy_without_pointer(*(struct ScopeData*)vpdata, decrefrefs, freenonrefs);
	if (freenonrefs)
		free(vpdata);
}

Object *scopeobj_newsub(Interp *interp, Object *parent, uint16_t nlocals)
{
	struct ScopeData *ptr = malloc(sizeof(*ptr));
	if (!ptr) {
		errobj_set_nomem(interp);
		return NULL;
	}

	if (!( ptr->locals = calloc(nlocals, sizeof(Object*)) ) && nlocals) {
		free(ptr);
		errobj_set_nomem(interp);
		return NULL;
	}

	ptr->nlocals = nlocals;

	if (parent == NULL) {
		ptr->nparents = 0;
		ptr->parents = malloc(0);
	} else {
		OBJECT_INCREF(parent);
		struct ScopeData *parent_data = parent->data.val;
		ptr->nparents = parent_data->nparents + 1;
		ptr->parents = malloc(ptr->nparents * sizeof *ptr->parents);
		memcpy(ptr->parents, parent_data->parents, parent_data->nparents * sizeof *parent_data->parents);
		ptr->parents[ptr->nparents - 1] = parent;
	}

	return object_new(interp, &scopeobj_type, (struct ObjData){
		.val = ptr,
		.destroy = scopedata_destroy,
	});
}

Object *scopeobj_newglobal(Interp *interp)
{
	Object *res = scopeobj_newsub(interp, NULL, (uint16_t)builtin_nobjects);
	if(!res)
		return NULL;

	struct ScopeData *sd = res->data.val;
	memcpy(sd->locals, builtin_objects, builtin_nobjects*sizeof(builtin_objects[0]));
	for (size_t i = 0; i < builtin_nobjects; i++)
		OBJECT_INCREF(sd->locals[i]);
	return res;
}

Object *scopeobj_getforlevel(Object *scope, size_t level)
{
	struct ScopeData *data = scope->data.val;
	assert(level <= data->nparents);
	if (level == data->nparents) return scope;
	else return data->parents[level];
}

Object **scopeobj_getlocalvarsptr(Object *scope)
{
	return ((struct ScopeData*) scope->data.val)->locals;
}


const struct Type scopeobj_type = { .methods = NULL, .nmethods = 0 };
