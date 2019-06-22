#include "scope.h"
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include "../builtins.h"
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
	struct Object *res = scopeobj_newsub(interp, NULL, (uint16_t)nbuiltins);
	if(!res)
		return NULL;

	struct ScopeData *sd = res->data.val;
	memcpy(sd->locals, builtins, nbuiltins*sizeof(builtins[0]));
	for (size_t i = 0; i < nbuiltins; i++)
		OBJECT_INCREF(sd->locals[i]);
	return res;
}

struct Object *scopeobj_getforlevel(struct Object *scope, size_t level)
{
#define PARENT(s) ( ((struct ScopeData*) (s)->data.val)->parent )

	// FIXME: this looks like it's inefficient lol
	size_t mylevel = 0;
	for (struct Object *par = PARENT(scope); par; par = PARENT(par))
		mylevel++;

	assert(level <= mylevel);
	for ( ; level < mylevel; level++)
		scope = PARENT(scope);

	return scope;

#undef PARENT
}

struct Object **scopeobj_getlocalvarptr(struct Object *scope, size_t i)
{
	return & ((struct ScopeData*) scope->data.val)->locals[i];
}


const struct Type scopeobj_type = { .attribs = NULL, .nattribs = 0 };
