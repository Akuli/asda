#include "bool.h"
#include <stdbool.h>
#include <stddef.h>
#include "../object.h"
#include "../type.h"

BoolObject boolobj_true = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);
BoolObject boolobj_false = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);
const struct Type boolobj_type = TYPE_BASIC_COMPILETIMECREATE(NULL, NULL, NULL, 0);

// https://stackoverflow.com/a/18636323
extern inline BoolObject *boolobj_c2asda(bool cbool);
extern inline bool boolobj_asda2c(BoolObject *asdabool);
