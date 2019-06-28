#include "gc.h"
#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "interp.h"
#include "objects/string.h"

static void refcount_debug_object(struct Object *obj, unsigned int is, unsigned int shouldB)
{
	printf("%p: refcount=%u (should be %u)\n    ", (void*)obj, is, shouldB);
	if (obj->type == &stringobj_type){
		const char *str;
		size_t len;
		if (stringobj_toutf8(obj, &str, &len)) {
			putchar('"');
			fwrite(str, 1, len, stdout);
			putchar('"');
		}
		else
			printf("(cannot print string)");
		printf("\n");
	} else {
		printf("unknown type %p\n", (void*)obj->type);
	}
}

// TODO: make this work for compile-time created objects too
void gc_refcountdebug(struct Interp *interp)
{
	// figure out what the refcounts should be by destroying so that only refcounts change
	for (struct Object *obj = interp->objliststart; obj; obj = obj->next) {
		obj->gcflag = obj->refcount;
		obj->refcount = UINT_MAX;
	}

	for (struct Object *obj = interp->objliststart; obj; obj = obj->next) {
		if (obj->data.destroy)
			obj->data.destroy(obj->data.val, true, false);
	}

	bool ok = true;
	for (struct Object *obj = interp->objliststart; obj; obj = obj->next) {
		unsigned int shouldB = UINT_MAX - obj->refcount;
		unsigned int is = obj->gcflag;
		if (is != shouldB) {
			if(ok) {
				printf("*** refcount issues ***\n");
				ok=false;
			}
			refcount_debug_object(obj, is, shouldB);
		}
	}
}
