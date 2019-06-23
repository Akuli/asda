#include "objtyp.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "gc.h"
#include "interp.h"


const struct Type object_type = { .attribs = NULL, .nattribs = 0 };


void object_destroy(struct Object *obj, bool decrefrefs, bool freenonrefs)
{
	/*
	if this fails, a compile-time created object is being decreffed too
	much (or not increffed enough, or ->interp of a runtime-created object
	has been set to NULL which should never happen)
	*/
	assert(obj->interp);

	if (obj->data.destroy)
		obj->data.destroy(obj->data.val, decrefrefs, freenonrefs);
	if (freenonrefs)
		free(obj);
}

struct Object *object_new(struct Interp *interp, const struct Type *type, struct ObjData od)
{
	assert(interp);
	struct Object *obj = malloc(sizeof(*obj));
	if (!obj) {
		goto error;
	}

	obj->type = type;
	obj->refcount = 1;
	obj->interp = interp;
	obj->data = od;

	if(!gc_addobject(interp, obj))
		goto error;

	return obj;

error:
	free(obj);
	if (od.destroy)
		od.destroy(od.val, true, true);
	return NULL;
}
