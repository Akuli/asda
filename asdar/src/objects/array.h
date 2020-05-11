// see also ../dynarray.h
#ifndef OBJECTS_ARRAY_H
#define OBJECTS_ARRAY_H

#include "../dynarray.h"
#include "../object.h"


typedef struct ArrayObject {
	struct ObjectHead head;
	DynArray(Object *) da;
} ArrayObject;

#endif   // OBJECTS_ARRAY_H
