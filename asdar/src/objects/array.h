// see also ../dynarray.h
#ifndef OBJECTS_ARRAY_H
#define OBJECTS_ARRAY_H

#include "../cfunc.h"
#include "../dynarray.h"
#include "../object.h"

typedef struct ArrayObject {
	struct ObjectHead head;

	/*	Can't use flexible struct member because then reallocing would screw
		up all the pointers to the array object. */
	DynArray(Object *) da;
} ArrayObject;

// for cfunc_addmany
extern const struct CFunc arrayobj_cfuncs[];

#endif   // OBJECTS_ARRAY_H
