#include <assert.h>
#include <stdbool.h>
#include <src/object.h>
#include <src/objects/bool.h>
#include "../util.h"


TEST(boolobj_c2asda_and_asda2c)
{
	unsigned int t = boolobj_true.head.refcount, f = boolobj_false.head.refcount;

	assert(boolobj_c2asda(true) == &boolobj_true);
	assert(boolobj_c2asda(false) == &boolobj_false);
	assert(boolobj_true.head.refcount == t+1);
	assert(boolobj_false.head.refcount == f+1);

	OBJECT_DECREF(&boolobj_true);
	OBJECT_DECREF(&boolobj_false);
	assert(boolobj_true.head.refcount == t);
	assert(boolobj_false.head.refcount == f);

	assert(boolobj_asda2c(&boolobj_true) == true);
	assert(boolobj_asda2c(&boolobj_false) == false);
	assert(boolobj_true.head.refcount == t);
	assert(boolobj_false.head.refcount == f);
}
