/* objects

Here is a complete usage example (with includes omitted):

	////////////////// objects/example.h ////////////////// 

	extern const struct Type exampleobj_type;

	typedef struct ExampleObject {
		OBJECT_HEAD
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

		ExampleObject *obj = object_new(interp, &exampleobj_type, destroy_exampleobj, sizeof(*obj));
		if (!obj) {
			free(customthing);
			return NULL;
		}

		obj->customthing = customthing;
		return obj;
	}

	const struct Type exampleobj_type = TYPE_BASIC_COMPILETIMECREATE(NULL, NULL, NULL, 0);
*/

#ifndef OBJECT_H
#define OBJECT_H

// IWYU pragma: no_forward_declare Object
#include <stdbool.h>
#include <stddef.h>
#include "interp.h"
#include "type.h"

// destroy function can be NULL
struct ObjData {
	void *val;
	void (*destroy)(void *val, bool decrefrefs, bool freenonrefs);
};

// also include objects/func.h if you need to do something with methods of types
struct FuncObject;


/*
look up "common initial members" if you are not familiar with this technique
any object can be casted to Object
Object can be usually casted to something more specific depending on the type
TODO: make the refcount atomic?
*/
#define OBJECT_HEAD \
	const struct Type *type; \
	void (*destroy)(struct Object *obj, bool decrefrefs, bool freenonrefs); \
	unsigned int refcount;       /* access this only with OBJECT_INCREF and OBJECT_DECREF */ \
	unsigned int gcflag;         /* for gc.c, don't use elsewhere */ \
	Interp *interp;              /* NULL for OBJECT_COMPILETIMECREATE objects */ \
	struct Object *prev, *next;  /* a doubly-linked list so that removing objects is O(1) */

typedef struct Object { OBJECT_HEAD } Object;

/*
Usage:

	ExampleObject obj = OBJECT_COMPILETIMECREATE(&exampleobj_type,
		.customfield = 1,
		.anotherfield = 2,
	);

if you don't want to set any fields not in OBJECT_HEAD, do OBJECT_COMPILETIMECREATE(&exampleobj_type, 0)
the 0 is needed because c standard
*/
#define OBJECT_COMPILETIMECREATE(TYPE, ...) { \
	/* OBJECT_HEAD fields not defined here get set to 0 or NULL by default */ \
	.type = (TYPE), \
	.refcount = 1, \
	.interp = NULL, \
	__VA_ARGS__ \
}


// decref evaluates the arg multiple times
// incref doesn't, but i don't recommend relying on it, might change in the future
#define OBJECT_INCREF(obj) (obj)->refcount++
#define OBJECT_DECREF(obj) do{  \
	if (--(obj)->refcount == 0) { \
		/* this should never happen for statically allocated objects */ \
		object_destroy((Object *)(obj), true, true); \
	} \
} while(0)

/*
returns an object with refcount 1, and all fields not in OBJECT_HEAD unset
destroy can be NULL
return type declared as void* to avoid a cast when calling object_new()
*/
void *object_new(Interp *interp, const struct Type *type,
	void (*destroy)(Object *obj, bool decrefrefs, bool freenonrefs),
	size_t sz);

// use decref instead of calling this yourself
void object_destroy(Object *obj, bool decrefrefs, bool freenonrefs);


#endif   // OBJECT_H
