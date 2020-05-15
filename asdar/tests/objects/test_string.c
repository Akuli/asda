// utf8 tests are in ../test_utf8.c

#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>
#include <src/object.h>
#include <src/objects/string.h>
#include "../util.h"

TEST(stringobj_new)
{
	// valgrind should complain if it assumes that there is '\0' at end
	char *ptr = malloc(5);
	assert(ptr);
	memcpy(ptr, "hello", 5);

	StringObject *obj = stringobj_new(interp, ptr, 5);
	assert(obj);
	assert(obj->utf8len == 5);
	assert(obj->utf8ct == NULL);
	assert_cstr_eq_cstr(obj->utf8rt, "hello");
	OBJECT_DECREF(obj);

	obj = stringobj_new_nocp(interp, ptr, 5);   // will free ptr
	assert(obj);
	assert(obj->utf8len == 5);
	assert(obj->utf8ct == NULL);
	assert_cstr_eq_cstr(obj->utf8rt, "hello");
	OBJECT_DECREF(obj);
}

static StringObject hello = STRINGOBJ_COMPILETIMECREATE("hello");

TEST(stringobj_compiletimecreate)
{
	assert(hello.head.refcount == 1);
	assert(hello.utf8len == 5);
	assert_cstr_eq_cstr(hello.utf8ct, "hello");
}

TEST(stringobj_getutf8)
{
	StringObject *hello2 = stringobj_new(interp, "hello", 5);
	assert(stringobj_getutf8(&hello) == hello.utf8ct);
	assert(stringobj_getutf8(hello2) == hello2->utf8rt);
	assert_cstr_eq_cstr(stringobj_getutf8(&hello), stringobj_getutf8(hello2));
	OBJECT_DECREF(hello2);
}

TEST(stringobj_new_format)
{
	StringObject *b = stringobj_new(interp, "b", 1);
	StringObject *str = stringobj_new_format(interp, "hello world, %s, %S, %U, %U, %B, %B, %d, %zu, %%",
		"a", b, (uint32_t)'c', (uint32_t)0xdddL, (unsigned char)'e', (unsigned char)0xf, -123, (size_t)456);

	assert_strobj_eq_cstr(str, "hello world, a, b, U+0063 'c', U+0DDD, 0x65 'e', 0x0f, -123, 456, %");

	OBJECT_DECREF(b);
	OBJECT_DECREF(str);
}
