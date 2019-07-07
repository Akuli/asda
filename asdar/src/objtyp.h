// objects and types

#ifndef OBJTYP_H
#define OBJTYP_H

// IWYU pragma: no_forward_declare ObjectStruct
#include <stdbool.h>
#include <stddef.h>
#include "interp.h"

// destroy function can be NULL
struct ObjData {
	void *val;
	void (*destroy)(void *val, bool decrefrefs, bool freenonrefs);
};

/* if you are a typedef hater

then please let this be, just compare this:

	Object *foo(Interp *interp, Object *bar, Object *baz, Object **spam, size_t nspam);

to this:

	struct Object *foo(struct Interp *interp, struct Object *bar, struct Object *baz, struct Object **spam, size_t nspam);

some function declarations actually use this struct many times!
*/
typedef struct ObjectStruct Object;

struct Type {
	Object **methods;
	size_t nmethods;
};

struct ObjectStruct {
	const struct Type *type;
	unsigned int refcount;       // TODO: atomic?
	unsigned int gcflag;         // gc.c uses this for an implementation-detaily thing
	Interp *interp;       // NULL for statically allocated objects
	struct ObjData data;

	// runtime created objects go into a doubly linked list
	// it is doubly linked to make removing objects from the list O(1)
	Object *prev;
	Object *next;
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

Destroys od on no mem, so you can do this:

	static Object *someobj_new(Interp *interp)
	{
		struct ObjData od;
		fill up od somehow;
		if (failure with filling) {
			destroy things that have been filled so far;
			set message to interp->errstr;
			return NULL;
		}

		return object_new(interp, someobj_type, od);
	}

Now od is destroyed correctly even if object_new() runs out of memory.
*/
Object *object_new(Interp *interp, const struct Type *type, struct ObjData od);

// use decref instead of calling this yourself
void object_destroy(Object *obj, bool decrefrefs, bool freenonrefs);

extern const struct Type object_type;


#endif   // OBJTYP_H
