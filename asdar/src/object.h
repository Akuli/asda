/* objects

Here is a complete usage example (with includes omitted):

	////////////////// objects/example.h ////////////////// 

	typedef struct ExampleObject {
		struct ObjectHead head;
		char *customthing;
	} ExampleObject;


	////////////////// objects/example.c ////////////////// 

	static void destroy_exampleobj(Object *obj, bool decrefrefs, bool freenonrefs)
	{
		ExampleObject *ex = (ExampleObject *) obj;
		if (freenonrefs)
			free(ex->customthing);
	}

	ExampleObject *exampleobj_new(Interp *interp)
	{
		char *customthing = malloc(123);
		if (!customthing) {
			errobj_set_nomem(interp);
			return NULL;
		}
		strcpy(customthing, "hello world");

		ExampleObject *obj = object_new(interp, destroy_exampleobj, sizeof(*obj));
		if (!obj) {
			free(customthing);
			return NULL;
		}

		obj->customthing = customthing;
		return obj;
	}
*/

#ifndef OBJECT_H
#define OBJECT_H

// IWYU pragma: no_forward_declare Object
#include <stdbool.h>
#include <stddef.h>
#include "interp.h"

// forward declare because this file gets included early in compilation
struct Interp;

// FIXME
struct ObjData {};

struct ObjectHead {
	void (*destroy)(struct Object *obj, bool decrefrefs, bool freenonrefs);
	struct Interp *interp;       // NULL for OBJECT_COMPILETIMECREATE objects
	struct Object *prev, *next;  // a doubly-linked list so that removing objects is fast
	unsigned int refcount;       // access this only with OBJECT_INCREF and OBJECT_DECREF.  TODO: atomic?
	unsigned int gcflag;         // for gc.c, don't use elsewhere
};

/*
look up "common initial members" if you are not familiar with this technique
a pointer to any object can be casted to Object*
some Object* pointers can be casted to e.g. StringObject*
*/
typedef struct Object { struct ObjectHead head; } Object;

/*
Usage:

	ExampleObject obj = {
		.head = OBJECT_COMPILETIME_HEAD,
		.customfield = 1,
		.anotherfield = 2,
	);

this is a weird macro because that's the only way for it to work in gcc and clang
*/
#define OBJECT_COMPILETIME_HEAD { .refcount = 1 }

// decref evaluates the arg multiple times
// incref doesn't, but i don't recommend relying on it, might change in the future
#define OBJECT_INCREF(obj) ((obj)->head.refcount++)
#define OBJECT_DECREF(obj) do{  \
	if (--(obj)->head.refcount == 0) { \
		/* this should never happen for compiletime objects */ \
		object_destroy((Object *)(obj), true, true); \
	} \
} while(0)

/*
returns an object with refcount 1, and all fields not in ObjectHead unset
destroy can be NULL
return type declared as void* to avoid a cast when calling object_new()
*/
void *object_new(
	struct Interp *interp,
	void (*destroy)(Object *obj, bool decrefrefs, bool freenonrefs),
	size_t sz);

// use decref instead of calling this yourself
void object_destroy(Object *obj, bool decrefrefs, bool freenonrefs);


#endif   // OBJECT_H
