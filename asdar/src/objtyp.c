#include "objtyp.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "interp.h"
#include "objects/err.h"


const struct Type object_type = { .methods = NULL, .nmethods = 0 };


void object_destroy(Object *obj, bool decrefrefs, bool freenonrefs)
{
	/*
	if this fails, a compile-time created object is being decreffed too
	much (or not increffed enough, or ->interp of a runtime-created object
	has been set to NULL which should never happen)
	*/
	assert(obj->interp);

	if (obj->data.destroy)
		obj->data.destroy(obj->data.val, decrefrefs, freenonrefs);

	if (freenonrefs) {
		if (obj->prev) {
			assert(obj != obj->interp->objliststart);
			obj->prev->next = obj->next;   // may be NULL
		} else {
			assert(obj == obj->interp->objliststart);
			obj->interp->objliststart = obj->next;   // may be NULL
		}
		if(obj->next)
			obj->next->prev = obj->prev;   // may be NULL

		free(obj);
	}
}

Object *object_new(Interp *interp, const struct Type *type, struct ObjData od)
{
	assert(interp);
	Object *obj = malloc(sizeof(*obj));
	if (!obj) {
		if (od.destroy)
			od.destroy(od.val, true, true);

		// errobj_set_nomem does NOT create an object with object_new for this
		// ituses a statically allocated no mem error object and does no allocations
		errobj_set_nomem(interp);
		return NULL;
	}

	obj->type = type;
	obj->refcount = 1;
	obj->interp = interp;
	obj->data = od;

	obj->prev = NULL;
	obj->next = obj->interp->objliststart;
	obj->interp->objliststart = obj;
	if(obj->next)
		obj->next->prev = obj;

	return obj;
}
