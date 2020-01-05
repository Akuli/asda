#include "interp.h"
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "dynarray.h"
#include "gc.h"
#include "object.h"
#include "objects/int.h"


void interp_init(Interp *interp, const char *argv0)
{
	interp->argv0 = argv0;
	interp->objliststart = NULL;
	interp->err = NULL;
	interp->firstmod = NULL;
	interp->basedir = NULL;

	memset(interp->intcache, 0, sizeof(interp->intcache));  // not strictly standard compliant but simpler than a loop
	dynarray_init(&interp->stack);
}

void interp_destroy(Interp *interp)
{
	for (size_t i = 0; i < sizeof(interp->intcache)/sizeof(interp->intcache[0]); i++)
		if (interp->intcache[i])
			OBJECT_DECREF(interp->intcache[i]);

	gc_refcountdebug(interp);

	Object *next;
	for (Object *obj = interp->objliststart; obj; obj = next){
		//printf("refcount cycling object %p\n", (void*)obj);
		next = obj->next;
		object_destroy(obj, false, true);
	}

	free(interp->stack.ptr);
}
