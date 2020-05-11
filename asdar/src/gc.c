#include "gc.h"
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include "interp.h"
#include "object.h"
#include "objects/string.h"

static void print_refcount_info(Object *obj, unsigned int is, unsigned int shouldB)
{
	printf("%p: refcount=%u (should be %u)\n", (void*)obj, is, shouldB);
}

// TODO: make this work for compile-time created objects too?
void gc_refcountdebug(Interp *interp)
{
	// figure out what the refcounts should be by destroying so that only refcounts change
	for (Object *obj = interp->objliststart; obj; obj = obj->head.next) {
		obj->head.gcflag = obj->head.refcount;
		obj->head.refcount = UINT_MAX;
	}

	for (Object *obj = interp->objliststart; obj; obj = obj->head.next) {
		if (obj->head.destroy)
			obj->head.destroy(obj, true, false);
	}

	bool ok = true;
	for (Object *obj = interp->objliststart; obj; obj = obj->head.next) {
		unsigned int shouldB = UINT_MAX - obj->head.refcount;
		unsigned int is = obj->head.gcflag;
		if (is != shouldB) {
			if(ok) {
				printf("*** refcount issues ***\n");
				ok=false;
			}
			print_refcount_info(obj, is, shouldB);
		}
	}
}
