#include "bool.h"
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include "../objtyp.h"

const struct Type boolobj_type = { .methods = NULL, .nmethods = 0 };
struct Object boolobj_true = OBJECT_COMPILETIMECREATE(&boolobj_type, NULL);
struct Object boolobj_false = OBJECT_COMPILETIMECREATE(&boolobj_type, NULL);

struct Object *boolobj_c2asda(bool cbool)
{
	struct Object *res = cbool ? &boolobj_true : &boolobj_false;
	OBJECT_INCREF(res);
	return res;
}

// asserts that the object is boolobj_true or boolobj_false
bool boolobj_asda2c(struct Object *asdabool)
{
	if(asdabool == &boolobj_true)
		return true;
	if(asdabool == &boolobj_false)
		return false;
	assert(0);
}
