#include "gc.h"
#include <assert.h>
#include <limits.h>
#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "interp.h"
#include "builtins.h"
#include "objects/string.h"

void gc_init(struct Gc *gc)
{
	gc->objects = NULL;
	gc->objectssz = 0;
	gc->objectslen = 0;
}

// FIXME: this is copy/pasta from runner.c
static bool ensure_objects_size(struct Interp *interp, size_t minsz)
{
	if (interp->gc.objectssz >= minsz)
		return true;

	size_t newsz;
	if (interp->gc.objectssz == 0)
		newsz = 10;
	else
		newsz = 2*interp->gc.objectssz;

	if (newsz < minsz)
		newsz = minsz;

	if (!( interp->gc.objects = realloc(interp->gc.objects, sizeof(struct Object*)*newsz) ))
	{
		interp_errstr_nomem(interp);
		return false;
	}
	interp->gc.objectssz = newsz;
	return true;
}

bool gc_addobject(struct Interp *interp, struct Object *obj)
{
	if(!ensure_objects_size(interp, interp->gc.objectslen + 1))
		return false;
	interp->gc.objects[interp->gc.objectslen++] = obj;
	//printf("now there are %zu objects\n", interp->gc.objectslen);
	return true;
}

void gc_onrefcount0(struct Interp *interp, struct Object *obj)
{
	// FIXME: this is awfully horrible
	for (size_t i = 0; i < interp->gc.objectslen; i++) {
		if (interp->gc.objects[i] == obj) {
			memmove(
				&interp->gc.objects[i],
				&interp->gc.objects[i+1],
				(interp->gc.objectslen - (i+1))*sizeof(struct Object*)
				);
			interp->gc.objectslen--;
			return;
		}
	}
	assert(0);
}


static void refcount_debug_object(struct Object *obj, unsigned int is, unsigned int shouldB)
{
	printf("%p: refcount=%u (should be %u)", (void*)obj, is, shouldB);
	printf("\n    ");
	if (obj->type == &stringobj_type){
		char *str;
		size_t len;
		if (stringobj_toutf8(obj, &str, &len)) {
			putchar('"');
			fwrite(str, 1, len, stdout);
			putchar('"');
			free(str);
		}
		else
			printf("(cannot print string)");
		printf("\n");
	} else {
		printf("unknown type %p\n", (void*)obj->type);
	}
}

// TODO: make this work for compile-time created objects too
static void refcount_debug(struct Gc gc)
{
	struct Object **ptr;
	struct Object **end = gc.objects + gc.objectslen;
	// figure out what the refcounts should be by destroying so that only refcounts change

	for (ptr = gc.objects; ptr < end; ptr++) {
		(*ptr)->gcflag = (*ptr)->refcount;
		(*ptr)->refcount = UINT_MAX;
	}

	for (ptr = gc.objects; ptr < end; ptr++) {
		if ((*ptr)->data.destroy)
			(*ptr)->data.destroy((*ptr)->data.val, true, false);
	}

	bool ok = true;
	for (ptr = gc.objects; ptr < end; ptr++) {
		unsigned int shouldB = UINT_MAX - (*ptr)->refcount;
		unsigned int is = (*ptr)->gcflag;
		if (is != shouldB) {
			if(ok) {
				printf("*** refcount issues ***\n");
				ok=false;
			}
			refcount_debug_object(*ptr, is, shouldB);
		}
	}
}

static void destroy_everything(struct Gc gc)
{
	for (struct Object **ptr = gc.objects; ptr < gc.objects + gc.objectslen; ptr++)
		object_destroy(*ptr, false, true);
}

void gc_quit(struct Gc gc)
{
	refcount_debug(gc);
	destroy_everything(gc);
	free(gc.objects);
}
