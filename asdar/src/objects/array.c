#include "array.h"
#include <stdbool.h>
#include <stdlib.h>
#include "../cfunc.h"
#include "../dynarray.h"
#include "../interp.h"
#include "../object.h"
#include "err.h"
#include "int.h"
#include "string.h"

static void destroy_array(Object *obj, bool decrefrefs, bool freenonrefs)
{
	ArrayObject *arr = (ArrayObject *) obj;
	if (decrefrefs) {
		for (size_t i = 0; i < arr->da.len; i++)
			OBJECT_DECREF(arr->da.ptr[i]);
	}
	if (freenonrefs)
		free(arr->da.ptr);
}

static Object *new_cfunc(Interp *interp, Object *const *args)
{
	ArrayObject *res = object_new(interp, destroy_array, sizeof(*res));
	if (!res)
		return NULL;

	dynarray_init(&res->da);
	return (Object *)res;
}

static Object *getlength_cfunc(Interp *interp, Object *const *args)
{
	ArrayObject *arr = (ArrayObject *)args[0];
	return (Object *) intobj_new_long(interp, (long)arr->da.len);
}

static bool push_cfunc(Interp *interp, Object *const *args)
{
	if (dynarray_push(interp, &( (ArrayObject *)args[0] )->da, args[1])) {
		OBJECT_INCREF(args[1]);
		return true;
	}
	return false;
}

static Object *pop_cfunc(Interp *interp, Object *const *args)
{
	ArrayObject *arr = (ArrayObject *)args[0];

	if (arr->da.len == 0) {
		errobj_set(interp, &errtype_value, "cannot pop from an empty array");
		return NULL;
	}
	return dynarray_pop(&arr->da);
}

static Object *get_cfunc(Interp *interp, Object *const *args)
{
	ArrayObject *arr = (ArrayObject *)args[0];
	IntObject *i = (IntObject *)args[1];

	if (!intobj_fits2long(i))
		goto bad_index;

	long val = intobj_getlong(i);
	if (val < 0 || val >= (long)arr->da.len)
		goto bad_index;

	Object *res = arr->da.ptr[val];
	OBJECT_INCREF(res);
	return res;

bad_index:
	(void)0;   // because c syntax
	char tmp[INTOBJ_TOCSTR_TMPSZ];
	const char *istr = intobj_tocstr(interp, i, tmp);
	if (istr)   // if intobj_tostrobj() failed then error has been set
		errobj_set(interp, &errtype_value, "cannot do get element %s from an array of length %zu", istr, arr->da.len);
	return false;
}

const struct CFunc arrayobj_cfuncs[] = {
	{ "Array.new", 1, true, { .ret = new_cfunc }},
	{ "Array.get_length", 1, true, { .ret = getlength_cfunc }},
	{ "Array.push", 2, false, { .noret = push_cfunc }},
	{ "Array.pop", 1, true, { .ret = pop_cfunc }},
	{ "Array.get", 2, true, { .ret = get_cfunc }},
	{0},
};
