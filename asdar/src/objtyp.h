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

// also include objects/func.h if you need to do something with methods of types
struct FuncObject;

struct Type {
	struct FuncObject **methods;
	size_t nmethods;
};


/*
other objects are created like this:

	struct SomeOtherObject {
		OBJECT_HEAD
		custom stuff here
	};

any object can be casted to 'struct Object'
'struct Object' can be usually casted to some other more specific struct
that depends on the type

TODO: make the refcount atomic?
*/
#define OBJECT_HEAD \
	const struct Type *type; \
	void (*destroy)(struct Object *obj, bool decrefrefs, bool freenonrefs); \
	unsigned int refcount;       /* access this only with OBJECT_INCREF and OBJECT_DECREF */ \
	unsigned int gcflag;         /* for gc.c, don't use elsewhere */ \
	Interp *interp;              /* NULL for OBJECT_COMPILETIMECREATE objects */ \
	struct Object *prev, *next;  /* a doubly-linked list so that removing objects is O(1) */

struct Object { OBJECT_HEAD };

/*
Usage:

	struct SomeObject obj = OBJECT_COMPILETIMECREATE(&someobj_type,
		.customfield = 1,
		.anotherfield = 2,
	);

if you don't want to set any custom fields, do OBJECT_COMPILETIMECREATE(&someobj_type, 0)
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
#define OBJECT_INCREF(obj) (obj)->refcount++
#define OBJECT_DECREF(obj) do{  \
	if (--(obj)->refcount == 0) { \
		/* this should never happen for statically allocated objects */ \
		object_destroy((struct Object *)(obj), true, true); \
	} \
} while(0)

/* returns an object with refcount 1, and all fields not in OBJECT_HEAD unset

Example:

	struct SomeObject {
		OBJECT_HEAD
		char *customthing;
	};

	static void destroy_someobj(struct Object *obj, bool decrefrefs, bool freenonrefs)
	{
		struct SomeObject *sobj = obj;
		free(sobj->customthing);
	}

	struct SomeObject *someobj_new(Interp *interp)
	{
		char *customthing = malloc(123);
		if (!customthing) {
			errobj_set_nomem(interp);
			return NULL;
		}
		strcpy(customthing, "hello world");

		struct SomeObject *obj = object_new(interp, &someobj_type, destroy_someobj, sizeof(*obj));
		if (!obj) {
			free(customthing);
			return NULL;
		}

		obj->customthing = customthing;
		return obj;
	}

destroy can be NULL
return type declared as void* to avoid a cast after calling object_new()
*/
void *object_new(Interp *interp, const struct Type *type,
	void (*destroy)(struct Object *obj, bool decrefrefs, bool freenonrefs),
	size_t sz);

// use decref instead of calling this yourself
void object_destroy(struct Object *obj, bool decrefrefs, bool freenonrefs);

extern const struct Type object_type;


#endif   // OBJTYP_H
