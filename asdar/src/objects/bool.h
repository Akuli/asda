#ifndef OBJECTS_BOOL_H
#define OBJECTS_BOOL_H

#include <stdbool.h>
#include "../objtyp.h"

extern const struct Type boolobj_type;

struct BoolObject {
	OBJECT_HEAD
};

extern struct BoolObject boolobj_true, boolobj_false;

// never fails, always returns a new reference
struct BoolObject *boolobj_c2asda(bool cbool);

// asserts that the object is boolobj_true or boolobj_false
bool boolobj_asda2c(struct BoolObject *asdabool);

/** Negate a Boolean
 * Returns a new reference
 */
struct BoolObject *boolobj_neg(struct BoolObject *obj);

#endif   // OBJECTS_BOOL_H
