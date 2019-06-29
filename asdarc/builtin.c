#include "builtin.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include "interp.h"
#include "objtyp.h"
#include "objects/bool.h"
#include "objects/func.h"
#include "objects/int.h"
#include "objects/string.h"


static bool print_impl(struct Interp *interp, struct ObjData data, struct Object **args, size_t nargs)
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
	return true;
}

static struct FuncObjData printdata = FUNCOBJDATA_COMPILETIMECREATE_NORET(print_impl);
static struct Object print = OBJECT_COMPILETIMECREATE(&funcobj_type_noret, &printdata);

struct Object* const builtin_objects[] = { &print, &boolobj_true, &boolobj_false };
const size_t builtin_nobjects = sizeof(builtin_objects)/sizeof(builtin_objects[0]);


const struct Type* const builtin_types[] = { &stringobj_type, &intobj_type, &boolobj_type, &object_type };
const size_t builtin_ntypes = sizeof(builtin_types)/sizeof(builtin_types[0]);
