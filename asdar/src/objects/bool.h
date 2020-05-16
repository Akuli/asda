#ifndef OBJECTS_BOOL_H
#define OBJECTS_BOOL_H

#include <assert.h>
#include <stdbool.h>
#include "../object.h"
#include "../cfunc.h"


typedef struct BoolObject {
	struct ObjectHead head;
} BoolObject;

extern BoolObject boolobj_true, boolobj_false;

// yes, non-static inline functions are defined in header files in c

// never fails, always returns a new reference
inline BoolObject *boolobj_c2asda(bool cbool)
{
	BoolObject *res = cbool ? &boolobj_true : &boolobj_false;
	OBJECT_INCREF(res);
	return res;
}

inline bool boolobj_asda2c(BoolObject *asdabool)
{
	assert(asdabool == &boolobj_true || asdabool == &boolobj_false);
	return (asdabool == &boolobj_true);
}

extern const struct CFunc boolobj_cfuncs[];

#endif   // OBJECTS_BOOL_H
