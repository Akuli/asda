#ifndef OBJECTS_BOOL_H
#define OBJECTS_BOOL_H

#include <stdbool.h>
#include "../objtyp.h"

extern const struct Type boolobj_type;

typedef struct BoolObject {
	OBJECT_HEAD
} BoolObject;

extern BoolObject boolobj_true, boolobj_false;

// never fails, always returns a new reference
BoolObject *boolobj_c2asda(bool cbool);

// asserts that the object is boolobj_true or boolobj_false
bool boolobj_asda2c(BoolObject *asdabool);

#endif   // OBJECTS_BOOL_H
