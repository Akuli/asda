// objects and types

#ifndef OBJTYP_H
#define OBJTYP_H

#include <stdbool.h>
#include <stddef.h>
#include "gc.h"

struct Interp;

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
	unsigned int gcflag;         // gc.c uses this for an implementation-detaily thing
	struct Interp *interp;       // NULL for statically allocated objects
	struct ObjData data;

	// runtime created objects go into a doubly linked list
	// it is doubly linked to make removing objects from the list O(1)
	struct Object *prev;
	struct Object *next;
};

#define OBJECT_COMPILETIMECREATE(TYPE, DATAVAL) { \
	/* fields not defined here get set to 0 or NULL by default */ \
	.type = (TYPE), \
	.refcount = 1, \
	.interp = NULL, \
	.data = { .val = (DATAVAL), .destroy = NULL }, \
}


// decref evaluates the arg multiple times
#define OBJECT_INCREF(obj) (obj)->refcount++
#define OBJECT_DECREF(obj) do{  \
	if (--(obj)->refcount == 0) { \
		/* this should never happen for statically allocated objects */ \
		object_destroy((obj), true, true); \
	} \
} while(0)

/* returns an object with refcount 1

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

extern const struct Type object_type;

// TODO: type_getattribute()


#endif   // OBJTYP_H
