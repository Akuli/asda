// see also ../dynarray.h
#ifndef OBJECTS_ARRAY_H
#define OBJECTS_ARRAY_H

#include "../dynarray.h"
#include "../interp.h"
#include "../object.h"
#include "../type.h"

extern const struct Type arrayobj_type;

typedef struct ArrayObject {
	OBJECT_HEAD
	DynArray(Object *) da;
} ArrayObject;

#endif   // OBJECTS_ARRAY_H
