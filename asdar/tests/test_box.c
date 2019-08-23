#include <src/objects/box.h>
#include <src/objects/int.h>
#include "util.h"

TEST(box)
{
	Object *a = (Object *) intobj_new_long(interp, 1234);
	Object *b = (Object *) intobj_new_long(interp, 5678);
	assert(a);
	assert(b);

	BoxObject *box = boxobj_new(interp);
	assert(box);
	assert(box->val == NULL);

	boxobj_set(box, a);
	assert(box->val == a);

	boxobj_set(box, b);
	assert(box->val == b);

	OBJECT_DECREF(a);
	OBJECT_DECREF(b);

	// valgrind shouldn't complain because box holds reference to b
	assert(intobj_cmp_long((IntObject *) box->val, 5678) == 0);
	OBJECT_DECREF(box);
}
