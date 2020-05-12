#include "interp.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "dynarray.h"
#include "gc.h"
#include "code.h"
#include "object.h"
#include "objects/int.h"


bool interp_init(Interp *interp, const char *argv0)
{
	interp->argv0 = argv0;
	interp->objliststart = NULL;
	interp->basedir = NULL;

	// not strictly standard compliant but simpler than a loop
	memset(interp->intcache, 0, sizeof(interp->intcache));

	dynarray_init(&interp->callstack);
	dynarray_init(&interp->objstack);
	dynarray_init(&interp->errstack);
	dynarray_init(&interp->code);

	// there must be always room for one more error to occur
	return dynarray_alloc_noerr(&interp->errstack, 1);
}

void interp_destroy(Interp *interp)
{
	for (size_t i = 0; i < sizeof(interp->intcache)/sizeof(interp->intcache[0]); i++) {
		if (interp->intcache[i])
			OBJECT_DECREF(interp->intcache[i]);
	}

	for (size_t i = 0; i < interp->code.len; i++) {
		codeop_destroy(interp->code.ptr[i]);
	}

	gc_refcountdebug(interp);

	Object *next;
	for (Object *obj = interp->objliststart; obj; obj = next){
		//printf("refcount cycling object %p\n", (void*)obj);
		next = obj->head.next;
		object_destroy(obj, false, true);
	}

	free(interp->callstack.ptr);
	free(interp->objstack.ptr);
	free(interp->errstack.ptr);
	free(interp->code.ptr);
}
