#include "builtin.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include "interp.h"
#include "objtyp.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/func.h"
#include "objects/int.h"
#include "objects/string.h"


static bool print_impl(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	assert(nargs == 1);
	assert(args[0]->type == &stringobj_type);

	const char *str;
	size_t len;
	if(!stringobj_toutf8(args[0], &str, &len))
		return false;

	for (const char *p = str; p < str+len; p++)
		putchar(*p);
	putchar('\n');
	*result = NULL;
	return true;
}

static struct FuncObjData printdata = FUNCOBJDATA_COMPILETIMECREATE(print_impl);
static Object print = OBJECT_COMPILETIMECREATE(&funcobj_type, &printdata);

Object* const builtin_objects[] = { &print, &boolobj_true, &boolobj_false };
const size_t builtin_nobjects = sizeof(builtin_objects)/sizeof(builtin_objects[0]);

const struct Type* const builtin_types[] = {
	&stringobj_type,
	&intobj_type,
	&boolobj_type,
	&object_type,
	&errobj_type_error,
	&errobj_type_nomem,
	&errobj_type_variable,
	&errobj_type_os,
};
const size_t builtin_ntypes = sizeof(builtin_types)/sizeof(builtin_types[0]);
