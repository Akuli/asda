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


static bool print_impl(Interp *interp, struct ObjData data, struct Object *const *args, size_t nargs, struct Object **result)
{
	assert(nargs == 1);
	assert(args[0]->type == &stringobj_type);
	struct StringObject *obj = (struct StringObject *)args[0];

	const char *str;
	size_t len;
	if(!stringobj_toutf8(obj, &str, &len))
		return false;

	for (const char *p = str; p < str+len; p++)
		putchar(*p);
	putchar('\n');
	*result = NULL;
	return true;
}

static struct FuncObject print = FUNCOBJ_COMPILETIMECREATE(print_impl);

struct Object* const builtin_objects[] = {
	(struct Object *)&print,
	(struct Object *)&boolobj_true,
	(struct Object *)&boolobj_false,
};
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
