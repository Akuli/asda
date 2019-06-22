#include "builtins.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "objtyp.h"
#include "objects/func.h"
#include "objects/string.h"


static bool print_impl(struct Interp *interp, struct Object **args, size_t nargs)
{
	assert(nargs == 1);
	assert(args[0]->type == &stringobj_type);

	char *str;
	size_t len;
	if(!stringobj_toutf8(args[0], &str, &len))
		return false;

	for (char *p = str; p < str+len; p++)
		putchar(*p);
	free(str);
	putchar('\n');
	return true;
}

static struct FuncObjData printdata = FUNCOBJDATA_COMPILETIMECREATE_NORET(print_impl);
static struct Object print = OBJECT_COMPILETIMECREATE(&funcobj_type_noret, &printdata);

struct Object* const builtins[] = { &print };
const size_t nbuiltins = sizeof(builtins)/sizeof(builtins[0]);
