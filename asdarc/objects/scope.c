#include "scope.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "../objtyp.h"


struct ScopeData {
	struct Object **locals;
	size_t nlocals;
	struct Object *parent;
};

static void scopedata_destroy_without_pointer(struct ScopeData data, bool decrefrefs, bool freenonrefs)
{
	if (decrefrefs) {
		if(data.parent)
			OBJECT_DECREF(data.parent);
		for (struct Object **ptr = data.locals; ptr < data.locals + data.nlocals; ptr++)
		{
			if(*ptr)
				OBJECT_DECREF(*ptr);
		}
	}
	if (freenonrefs)
		free(data.locals);
}

static void scopedata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	scopedata_destroy_without_pointer(*(struct ScopeData*)vpdata, decrefrefs, freenonrefs);
	if (freenonrefs)
		free(vpdata);
}


struct Object *scopeobj_newsub(struct Interp *interp, struct Object *parent, uint16_t nlocals)
{
	struct ScopeData *ptr = malloc(sizeof(*ptr));
	if (!ptr) {
		interp_errstr_nomem(interp);
		return NULL;
	}

	if (!( ptr->locals = calloc(nlocals, sizeof(struct Object*)) )) {
		free(ptr);
		interp_errstr_nomem(interp);
		return NULL;
	}

	ptr->nlocals = nlocals;
	ptr->parent = parent;
	if(parent)
		OBJECT_INCREF(parent);

	return object_new(interp, &scopeobj_type, (struct ObjData){
		.val = ptr,
		.destroy = scopedata_destroy,
	});
}

struct Object *scopeobj_newglobal(struct Interp *interp)
{
	// TODO: add variables
	return scopeobj_newsub(interp, NULL, 0);
}


const struct Type scopeobj_type = { .attribs = NULL, .nattribs = 0 };
