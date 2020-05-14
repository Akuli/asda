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


void interp_init(Interp *interp, const char *argv0)
{
	*interp = (Interp){0};
	interp->argv0 = argv0;
	dynarray_init(&interp->code);
	dynarray_init(&interp->mods);
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

	for (size_t i = 0; i < interp->mods.len; i++) {
		free(interp->mods.ptr[i].srcpathabs);
		free(interp->mods.ptr[i].bcpathabs);
		free(interp->mods.ptr[i].bcpathrel);
	}

	free(interp->code.ptr);
	free(interp->mods.ptr);
	free(interp->basedir);
}
