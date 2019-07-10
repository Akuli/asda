#include <assert.h>
#include <stdlib.h>
#include <src/dynarray.h>
#include "util.h"


// needed for passing it to a function
typedef DynArray(int) DynArrayOfInt;

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

	int fourfivesix[] = {4,5,6};   // needed because c macros are awesome
	int *nullptr = NULL;           // needed to avoid a "clever" gcc warning and to annoy C++ people

	bool ok;
	ok = dynarray_push(&da, 1); assert(ok);
	ok = dynarray_push(&da, 2); assert(ok);
	ok = dynarray_push(&da, 3); assert(ok);
	ok = dynarray_pushmany(&da, nullptr, 0); assert(ok);
	ok = dynarray_pushmany(&da, fourfivesix, 2); assert(ok);

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

	bool ok = dynarray_alloc(&da, 0);
	assert(ok);
	assert(da.alloc == 0);
	assert(da.len == 0);
	assert(da.ptr == NULL);

	dynarray_shrink2fit(&da);
	assert(da.alloc == 0);
	assert(da.len == 0);
	assert(da.ptr == NULL);
}
