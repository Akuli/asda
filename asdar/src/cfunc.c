#include "cfunc.h"
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "interp.h"
#include "object.h"
#include "objects/array.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/int.h"
#include "objects/string.h"

// binary search, can't use stdlib bsearch because it returns NULL for no match
static size_t find_insert_index(
	const struct CFunc **arr, size_t arrlen, const char *name)
{
	size_t lo = 0, hi = arrlen;
	while (lo < hi) {
		size_t mid = (lo+hi)/2;
		int c = strcmp(name, arr[mid]->name);

		assert(c != 0);    // if this fails, there are two functions with same name
		if (c < 0)
			hi = mid;
		else
			lo = mid+1;
	}
	return lo;
}

bool cfunc_addmany(Interp *interp, const struct CFunc *cfuncs)
{
	// TODO: optimize by not memmoving same things several times?
	for (size_t i = 0; cfuncs[i].name; i++) {
		if (!dynarray_alloc(interp, &interp->cfuncs, interp->cfuncs.len + 1))
			return false;

		size_t idx = find_insert_index(interp->cfuncs.ptr, interp->cfuncs.len, cfuncs[i].name);
		memmove(
			&interp->cfuncs.ptr[idx + 1],
			&interp->cfuncs.ptr[idx],
			(interp->cfuncs.len - idx) * sizeof(interp->cfuncs.ptr[0]));
		interp->cfuncs.ptr[idx] = &cfuncs[i];
		interp->cfuncs.len++;
	}

	return true;
}


static int cfunc_comparing_callback(const void *nameptr, const void *arrptr)
{
	const char *name = nameptr;
	const struct CFunc *const *cf = arrptr;
	return strcmp(name, (*cf)->name);
}

const struct CFunc *cfunc_get(Interp *interp, const char *name)
{
	const struct CFunc **res = bsearch(
		name,
		interp->cfuncs.ptr,
		interp->cfuncs.len,
		sizeof(interp->cfuncs.ptr[0]),
		cfunc_comparing_callback);

	if (res)
		return *res;
	return NULL;
}
