// objects and types

#ifndef OBJTYP_H
#define OBJTYP_H

#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include "interp.h"

// destroy function can be NULL
struct ObjData {
	void *val;
	void (*destroy)(void *val, bool decrefrefs, bool freenonrefs);
};

struct TypeAttribute {
	bool ismethod;
	struct Object *value;
};

struct Type {
	const struct TypeAttribute *attribs;
	size_t nattribs;
};

struct Object {
	const struct Type *type;
	unsigned int refcount;       // TODO: atomic?
	struct Interp *interp;       // NULL for statically allocated objects
	struct ObjData data;
};


// TODO: implement this
static void gc_onrefcount0(struct Interp *i, struct Object *o) {}

// decref evaluates the arg multiple times
#define OBJECT_INCREF(obj) (obj)->refcount++
#define OBJECT_DECREF(obj) do{  \
	if (--(obj)->refcount == 0) { \
		/* this should never happen for statically allocated objects */ \
		gc_onrefcount0((obj)->interp, (obj)); \
		object_destroy((obj), true, true); \
	} \
} while(0)

/* returns an object with no data and refcount 1

On no mem, destroys od and returns NULL. This means that you can do this:

	static struct Object *someobj_new(struct Interp *interp)
	{
		struct ObjData od;
		fill up od somehow;
		if (failure with filling) {
			destroy things that have been filled so far;
			return NULL;
		}

		return object_new(interp, someobj_type, od);
	}

Now od is destroyed correctly even if object_new() runs out of memory.
*/
struct Object *object_new(struct Interp *interp, const struct Type *type, struct ObjData od);

// use decref instead of calling this yourself
void object_destroy(struct Object *obj, bool decrefrefs, bool freenonrefs);

extern const struct Type *const object_type;

// TODO: type_getattribute()


#endif   // OBJTYP_H
