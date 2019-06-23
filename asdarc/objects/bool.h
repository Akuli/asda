#ifndef OBJECTS_BOOL_H
#define OBJECTS_BOOL_H

#include "../objtyp.h"

extern struct Object boolobj_true, boolobj_false;
extern const struct Type boolobj_type;

// never fails, always returns a new reference
struct Object *boolobj_c2asda(bool cbool);

// asserts that the object is boolobj_true or boolobj_false
bool boolobj_asda2c(struct Object *asdabool);

#endif   // OBJECTS_BOOL_H
