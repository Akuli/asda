#include "bool.h"
#include <stdbool.h>
#include <stddef.h>
#include "../object.h"

BoolObject boolobj_true = { .head = OBJECT_COMPILETIME_HEAD };
BoolObject boolobj_false = { .head = OBJECT_COMPILETIME_HEAD };

// https://stackoverflow.com/a/18636323
extern inline BoolObject *boolobj_c2asda(bool cbool);
extern inline bool boolobj_asda2c(BoolObject *asdabool);
