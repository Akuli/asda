#ifndef OBJECTS_BOOL_H
#define OBJECTS_BOOL_H

#include <stdbool.h>
#include "../objtyp.h"

extern Object boolobj_true, boolobj_false;
extern const struct Type boolobj_type;

// never fails, always returns a new reference
Object *boolobj_c2asda(bool cbool);

// asserts that the object is boolobj_true or boolobj_false
bool boolobj_asda2c(Object *asdabool);

/** Negate a Boolean
 * Returns a new reference
 */
Object *boolobj_neg(Object *obj);

#endif   // OBJECTS_BOOL_H
