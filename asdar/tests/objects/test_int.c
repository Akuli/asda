#include <assert.h>
#include <stdbool.h>
#include <src/object.h>
#include <src/objects/int.h>
#include "../util.h"

#define MAX_ABS_VALUE 50

TEST(intobj_new_long_and_cmp)
{
	IntObject *minusone = intobj_new_long(interp, -1);
	IntObject *twentyfour = intobj_new_long(interp, 24);   // https://www.youtube.com/watch?v=RkP_OGDCLY0
	IntObject *forty = intobj_new_long(interp, 40);
	IntObject *fourty = intobj_new_long(interp, 40);

	assert(intobj_cmp(forty, forty) == 0);
	assert(intobj_cmp(forty, fourty) == 0);

	assert(intobj_cmp(twentyfour, forty) < 0);
	assert(intobj_cmp(forty, twentyfour) > 0);

	assert(intobj_cmp(twentyfour, minusone) > 0);
	assert(intobj_cmp(minusone, twentyfour) < 0);

	assert(intobj_cmp_long(twentyfour, 10) > 0);
	assert(intobj_cmp_long(twentyfour, 18) > 0);
	assert(intobj_cmp_long(twentyfour, 24) == 0);
	assert(intobj_cmp_long(twentyfour, 25) < 0);
	assert(intobj_cmp_long(twentyfour, 30) < 0);
	assert(intobj_cmp_long(twentyfour, 31) < 0);
	assert(intobj_cmp_long(twentyfour, 45) < 0);

	OBJECT_DECREF(minusone);
	OBJECT_DECREF(twentyfour);
	OBJECT_DECREF(forty);
	OBJECT_DECREF(fourty);
}

TEST(intobj_addsubmulneg)
{
	IntObject *minustwo = intobj_new_long(interp, -2);
	IntObject *seven = intobj_new_long(interp, 7);

	IntObject *add = intobj_add(interp, minustwo, seven);
	IntObject *sub = intobj_sub(interp, minustwo, seven);
	IntObject *mul = intobj_mul(interp, minustwo, seven);
	IntObject *neg = intobj_neg(interp, minustwo);

	OBJECT_DECREF(minustwo);
	OBJECT_DECREF(seven);

	assert(intobj_cmp_long(add, 5) == 0);
	assert(intobj_cmp_long(sub, -9) == 0);
	assert(intobj_cmp_long(mul, -14) == 0);
	assert(intobj_cmp_long(neg, 2) == 0);

	OBJECT_DECREF(add);
	OBJECT_DECREF(sub);
	OBJECT_DECREF(mul);
	OBJECT_DECREF(neg);
}

TEST(intobj_new_bebytes)
{
	unsigned char byt[] = { 0x7, 0x5b, 0xcd, 0x15 };
	IntObject *pos = intobj_new_bebytes(interp, byt, sizeof byt, false);
	IntObject *neg = intobj_new_bebytes(interp, byt, sizeof byt, true);
	assert(intobj_cmp_long(pos, 123456789L) == 0);
	assert(intobj_cmp_long(neg, -123456789L) == 0);
	OBJECT_DECREF(pos);
	OBJECT_DECREF(neg);
}

TEST(intobj_tostring)
{
	// TODO
}
