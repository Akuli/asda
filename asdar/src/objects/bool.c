#include "bool.h"
#include <stdbool.h>
#include <stddef.h>
#include "../object.h"

BoolObject boolobj_true = { .head = object_compiletime_head };
BoolObject boolobj_false = { .head = object_compiletime_head };

// https://stackoverflow.com/a/18636323
extern inline BoolObject *boolobj_c2asda(bool cbool);
extern inline bool boolobj_asda2c(BoolObject *asdabool);
