#include "object.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "interp.h"
#include "type.h"
#include "objects/err.h"


const struct Type object_type = TYPE_BASIC_COMPILETIMECREATE(NULL, 0, NULL);


void object_destroy(Object *obj, bool decrefrefs, bool freenonrefs)
{
	/*
	if this fails, a compile-time created object is being decreffed too
	much (or not increffed enough, or ->interp of a runtime-created object
	has been set to NULL which should never happen)
	*/
	assert(obj->interp);

	if (obj->destroy) {
		obj->destroy(obj, decrefrefs, freenonrefs);
	}

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

void *object_new(Interp *interp, const struct Type *type,
	void (*destroy)(Object *, bool, bool),
	size_t sz)
{
	assert(interp);

	assert(sz >= sizeof(Object));
	Object *obj = malloc(sz);
	if (!obj) {
		// errobj_set_nomem does NOT create an object with object_new for this
		// ituses a statically allocated no mem error object and does no allocations
		errobj_set_nomem(interp);
		return NULL;
	}

	obj->type = type;
	obj->destroy = destroy;
	obj->refcount = 1;
	// gcflag left uninitialized
	obj->interp = interp;

	obj->prev = NULL;
	obj->next = interp->objliststart;
	interp->objliststart = obj;
	if(obj->next)
		obj->next->prev = obj;

	return obj;
}
