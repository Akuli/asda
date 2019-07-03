// utf8 tests are in ../test_utf8.c

#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <src/objtyp.h>
#include <src/objects/string.h>
#include "../util.h"

// this also tests stringobj_toutf8, there are no other tests for that
static void assert_object_equals_cstr(Object *obj, const char *cstr)
{
	const char *buf1, *buf2;
	size_t len1, len2;
	bool ok1 = stringobj_toutf8(obj, &buf1, &len1);
	bool ok2 = stringobj_toutf8(obj, &buf2, &len2);
	assert(ok1 && ok2);
	assert(len1 == len2);
	assert(buf1 == buf2);

	assert(len1 == strlen(cstr));
	assert(memcmp(cstr, buf1, len1) == 0);
}

TEST(stringobj_new_different_ways)
{
	const char *cstrs[] = { "abc", "" };

	for (size_t ii = 0; ii < sizeof(cstrs)/sizeof(cstrs[0]); ii++) {
		const char *cstr = cstrs[ii];

		uint32_t *buf = malloc(sizeof(buf[0]) * strlen(cstr));
		assert(buf);
		uint32_t buf2[50];
		for (size_t i = 0; cstr[i]; i++)
			buf[i] = buf2[i] = (unsigned char)cstr[i];

		Object *objs[] = {
			stringobj_new_nocpy(interp, buf, strlen(cstr)),
			stringobj_new(interp, buf2, strlen(cstr)),
			stringobj_new_utf8(interp, cstr, strlen(cstr)),
		};
		buf2[0] = 'x';   // should not screw up anything

		for (size_t i = 0; i < sizeof(objs)/sizeof(objs[0]); i++) {
			assert(objs[i]);
			assert_object_equals_cstr(objs[i], cstr);
			OBJECT_DECREF(objs[i]);
		}
	}
}
