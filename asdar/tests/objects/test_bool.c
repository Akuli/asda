#include <assert.h>
#include <stdbool.h>
#include <src/objtyp.h>
#include <src/objects/bool.h>
#include "../util.h"


TEST(boolobj_c2asda_and_asda2c)
{
	unsigned int t = boolobj_true.refcount, f = boolobj_false.refcount;

	assert(boolobj_c2asda(true) == &boolobj_true);
	assert(boolobj_c2asda(false) == &boolobj_false);
	assert(boolobj_true.refcount == t+1);
	assert(boolobj_false.refcount == f+1);

	OBJECT_DECREF(&boolobj_true);
	OBJECT_DECREF(&boolobj_false);
	assert(boolobj_true.refcount == t);
	assert(boolobj_false.refcount == f);

	assert(boolobj_asda2c(&boolobj_true) == true);
	assert(boolobj_asda2c(&boolobj_false) == false);
	assert(boolobj_true.refcount == t);
	assert(boolobj_false.refcount == f);
}
