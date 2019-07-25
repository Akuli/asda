#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <src/dynarray.h>
#include "util.h"


typedef DynArray(int) DynArrayOfInt;   // needed for passing it to a function

static void check_12745(DynArrayOfInt da)
{
	assert(da.len == 5);
	assert(da.alloc >= 5);
	for (int i = 0; i < 5; i++) {
		int val = i+1;
		if (val == 3)
			val = 7;
		assert(da.ptr[i] == val);
	}
}

TEST(dynarray_basic_stuff)
{
	DynArrayOfInt da;
	dynarray_init(&da);

	bool ok =
		dynarray_push(interp, &da, 1) &&
		dynarray_push(interp, &da, 2) &&
		dynarray_push(interp, &da, 3) &&
		dynarray_push(interp, &da, 4) &&
		dynarray_push(interp, &da, 5);
	assert(ok);

	da.ptr[2] = 7;
	check_12745(da);

	dynarray_shrink2fit(&da);
	assert(da.alloc == 5);
	check_12745(da);

	int i;
	i = dynarray_pop(&da); assert(i == 5);
	i = dynarray_pop(&da); assert(i == 4);
	i = dynarray_pop(&da); assert(i == 7);
	i = dynarray_pop(&da); assert(i == 2);
	i = dynarray_pop(&da); assert(i == 1);
	assert(da.len == 0);

	free(da.ptr);
}

TEST(dynarray_zero_size)
{
	DynArray(int) da;
	dynarray_init(&da);
	assert(da.alloc == 0);
	assert(da.len == 0);
	assert(da.ptr == NULL);

	bool ok = dynarray_alloc(interp, &da, 0);
	assert(ok);
	assert(da.alloc == 0);
	assert(da.len == 0);
	assert(da.ptr == NULL);

	dynarray_shrink2fit(&da);
	assert(da.alloc == 0);
	assert(da.len == 0);
	assert(da.ptr == NULL);
}

TEST(dynarray_type_casts_nicely)
{
	DynArray(char) da;
	dynarray_init(&da);
	bool ok =
		dynarray_push(interp, &da, 'a') &&
		dynarray_push(interp, &da, (long long)'s') &&
		dynarray_push(interp, &da, (unsigned long long)'d') &&
		dynarray_push(interp, &da, (unsigned char)'a') &&
		dynarray_push(interp, &da, 0);
	assert(ok);

	assert_cstr_eq_cstr(da.ptr, "asda");
	free(da.ptr);
}

// the bug has been fixed if this test doesn't leak memory
TEST(dynarray_old_memory_leaking_bug)
{
	DynArray(int) da;
	dynarray_init(&da);
	bool ok = dynarray_push(interp, &da, 1);
	assert(ok);
	int val = dynarray_pop(&da);
	assert(val == 1);
	dynarray_shrink2fit(&da);
}
