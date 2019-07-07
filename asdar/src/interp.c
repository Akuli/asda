#include "interp.h"
#include <stdio.h>
#include <stdbool.h>
#include "gc.h"
#include "objtyp.h"
#include "objects/scope.h"


bool interp_init(Interp *interp, const char *argv0)
{
	interp->argv0 = argv0;
	interp->err = NULL;
	interp->objliststart = NULL;
	interp->firstmod = NULL;

	if (!( interp->builtinscope = scopeobj_newglobal(interp) ))
		return false;
	return true;
}

void interp_destroy(Interp *interp)
{
	if (interp->builtinscope)
		OBJECT_DECREF(interp->builtinscope);
	gc_refcountdebug(interp);

	Object *next;
	for (Object *obj = interp->objliststart; obj; obj = next){
		//printf("refcount cycling object %p\n", (void*)obj);
		next = obj->next;
		object_destroy(obj, false, true);
	}
}
