// utf8 tests are in ../test_utf8.c

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <src/object.h>
#include <src/objects/string.h>
#include "../util.h"

TEST(stringobj_toutf8)
{
	StringObject *obj = stringobj_new(interp, (uint32_t[]){'h','e','l','l','o'}, 5);
	assert(obj);

	const char *buf1, *buf2;
	size_t len1, len2;
	bool ok1 = stringobj_toutf8(obj, &buf1, &len1);
	bool ok2 = stringobj_toutf8(obj, &buf2, &len2);

	assert(ok1 && ok2);
	assert(len1 == 5);
	assert(len2 == 5);
	assert_cstr_eq_cstr(buf1, "hello");
	assert_cstr_eq_cstr(buf2, "hello");

	OBJECT_DECREF(obj);
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

		StringObject *objs[] = {
			stringobj_new_nocpy(interp, buf, strlen(cstr)),
			stringobj_new(interp, buf2, strlen(cstr)),
			stringobj_new_utf8(interp, cstr, strlen(cstr)),
		};
		buf2[0] = 'x';   // should not screw up anything

		for (size_t i = 0; i < sizeof(objs)/sizeof(objs[0]); i++) {
			assert(objs[i]);
			assert_strobj_eq_cstr(objs[i], cstr);
			OBJECT_DECREF(objs[i]);
		}
	}
}

static StringObject hello = STRINGOBJ_COMPILETIMECREATE('h','e','l','l','o');

TEST(stringobj_data_compiletimecreate)
{
	StringObject *obj = stringobj_new_format(interp, "hello", sizeof("hello")-1);
	assert(obj);

	const char *chjunk;
	size_t szjunk;
	bool ok = stringobj_toutf8(obj, &chjunk, &szjunk);   // adds utf8cache and utf8cachelen to the data
	assert(ok);

	int i = 0;
	for (StringObject *s = obj; i++ < 2; s = &hello) {
		assert(s->len == 5);
		assert(s->val[0] == 'h');
		assert(s->val[1] == 'e');
		assert(s->val[2] == 'l');
		assert(s->val[3] == 'l');
		assert(s->val[4] == 'o');

		assert(strcmp(s->utf8cache, "hello") == 0);
		assert(s->utf8cachelen == 5);
	}

	OBJECT_DECREF(obj);
}

TEST(stringobj_new_format)
{
	StringObject *b = stringobj_new_utf8(interp, "b", 1);
	StringObject *str = stringobj_new_format(interp, "hello world, %s, %S, %U, %U, %B, %B, %d, %zu, %%",
		"a", b, (uint32_t)'c', (uint32_t)0xdddL, (unsigned char)'e', (unsigned char)0xf, -123, (size_t)456);

	assert_strobj_eq_cstr(str, "hello world, a, b, U+0063 'c', U+0DDD, 0x65 'e', 0x0f, -123, 456, %");

	OBJECT_DECREF(b);
	OBJECT_DECREF(str);
}
