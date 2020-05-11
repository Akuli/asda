#include "array.h"
#include <stdbool.h>
#include <stdlib.h>
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

static struct Object* array_constructor(Interp *interp, const struct Type *arrtype, struct Object *const *args, size_t nargs)
{
	ArrayObject *res = object_new(interp, destroy_array, sizeof(*res));
	if (!res)
		return NULL;

	dynarray_init(&res->da);
	return (Object *)res;
}

static bool length_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	ArrayObject *arr = (ArrayObject *)args[0];
	return !!( *result = (Object *) intobj_new_long(interp, (long)arr->da.len) );
}
//FUNCOBJ_COMPILETIMECREATE(length, &intobj_type, { &arrayobj_type });

static bool push_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	if (dynarray_push(interp, &( (ArrayObject *)args[0] )->da, args[1])) {
		OBJECT_INCREF(args[1]);
		*result = NULL;
		return true;
	}
	return false;
}
//FUNCOBJ_COMPILETIMECREATE(push, NULL, { &arrayobj_type, &type_object });

static bool pop_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	ArrayObject *arr = (ArrayObject *)args[0];

	if (arr->da.len == 0) {
		errobj_set(interp, &errobj_type_value, "cannot pop from an empty array");
		return false;
	}

	*result = dynarray_pop(&arr->da);
	return true;
}
//FUNCOBJ_COMPILETIMECREATE(pop, &type_object, { &arrayobj_type });

static bool get_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	ArrayObject *arr = (ArrayObject *)args[0];
	IntObject *i = (IntObject *)args[1];

	if (i->spilled || i->val.lon < 0 || i->val.lon >= (long)arr->da.len) {
		StringObject *istr = intobj_tostrobj(interp, i);
		if (istr) {   // an error has been already set if intobj_tostrobj() failed
			errobj_set(interp, &errobj_type_value, "cannot do get element %S from an array of length %zu", istr, arr->da.len);
			OBJECT_DECREF(istr);
		}
		return false;
	}

	*result = arr->da.ptr[i->val.lon];
	OBJECT_INCREF(*result);
	return true;
}
//FUNCOBJ_COMPILETIMECREATE(get, &type_object, { &arrayobj_type, &intobj_type });
