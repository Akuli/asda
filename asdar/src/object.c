#include "object.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "interp.h"
#include "objects/err.h"


void object_destroy(Object *obj, bool decrefrefs, bool freenonrefs)
{
	Interp *interp = obj->head.interp;

	/*
	if this fails, a compile-time created object is being decreffed too
	much (or not increffed enough, or ->interp of a runtime-created object
	has been set to NULL which should never happen)
	*/
	assert(interp);

	if (obj->head.destroy)
		obj->head.destroy(obj, decrefrefs, freenonrefs);

	if (freenonrefs) {
		if (obj->head.prev) {
			assert(obj != interp->objliststart);
			obj->head.prev->head.next = obj->head.next;   // may be NULL
		} else {
			assert(obj == interp->objliststart);
			interp->objliststart = obj->head.next;   // may be NULL
		}
		if(obj->head.next)
			obj->head.next->head.prev = obj->head.prev;   // may be NULL

		free(obj);
	}
}

void *object_new(Interp *interp, void (*destroy)(Object *, bool, bool), size_t sz)
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

	obj->head = (struct ObjectHead) {
		.destroy = destroy,   // may be NULL
		.interp = interp,
		.refcount = 1,
		.next = interp->objliststart,   // may be NULL
	};

	if (interp->objliststart)
		interp->objliststart->head.prev = obj;
	interp->objliststart = obj;

	return obj;
}
