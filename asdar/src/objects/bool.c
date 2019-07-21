#include "bool.h"
#include <stddef.h>
#include "../objtyp.h"

BoolObject boolobj_true = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);
BoolObject boolobj_false = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);
const struct Type boolobj_type = { .methods = NULL, .nmethods = 0 };

// https://stackoverflow.com/a/18636323
extern inline BoolObject *boolobj_c2asda(bool cbool);
extern inline bool boolobj_asda2c(BoolObject *asdabool);
