#include "interp.h"
#include <stdio.h>
#include <stdbool.h>
#include <string.h>
#include "gc.h"
#include "object.h"
#include "objects/int.h"
#include "objects/scope.h"


bool interp_init(Interp *interp, const char *argv0)
{
	interp->argv0 = argv0;
	interp->err = NULL;
	interp->objliststart = NULL;
	interp->firstmod = NULL;

	// not strictly standard compliant but simpler than a loop
	memset(interp->intcache, 0, sizeof(interp->intcache));

	return !!( interp->builtinscope = scopeobj_newglobal(interp) );
}

void interp_destroy(Interp *interp)
{
	if (interp->builtinscope)
		OBJECT_DECREF(interp->builtinscope);
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
}
