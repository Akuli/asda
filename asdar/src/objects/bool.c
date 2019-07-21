#include "bool.h"
#include <stddef.h>
#include "../objtyp.h"

BoolObject boolobj_true = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);
BoolObject boolobj_false = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);
const struct Type boolobj_type = { .methods = NULL, .nmethods = 0 };
