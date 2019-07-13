#include "bool.h"
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include "../objtyp.h"

struct BoolObject boolobj_true = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);
struct BoolObject boolobj_false = OBJECT_COMPILETIMECREATE(&boolobj_type, 0);

struct BoolObject *boolobj_c2asda(bool cbool)
{
	struct BoolObject *res = cbool ? &boolobj_true : &boolobj_false;
	OBJECT_INCREF(res);
	return res;
}

bool boolobj_asda2c(struct BoolObject *asdabool)
{
	assert(asdabool == &boolobj_true || asdabool == &boolobj_false);
	return (asdabool == &boolobj_true);
}

struct BoolObject *boolobj_neg(struct BoolObject *obj) {
	return boolobj_c2asda(!boolobj_asda2c(obj));
}

const struct Type boolobj_type = { .methods = NULL, .nmethods = 0 };
