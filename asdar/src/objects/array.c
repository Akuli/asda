#include <stdlib.h>
#include "../dynarray.h"
#include "../interp.h"
#include "../type.h"
#include "array.h"

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
	ArrayObject *res = object_new(interp, arrtype, destroy_array, sizeof(*res));
	if (!res)
		return NULL;

	dynarray_init(&res->da);
	return (Object *)res;
}

const struct Type arrayobj_basetype = TYPE_BASIC_COMPILETIMECREATE(NULL, array_constructor, NULL, 0);
