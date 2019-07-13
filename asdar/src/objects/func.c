#include "func.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "../interp.h"
#include "../objtyp.h"
#include "err.h"

const struct Type funcobj_type = { .methods = NULL, .nmethods = 0 };

bool funcobj_call(
	Interp *interp, struct FuncObject *f,
	struct Object *const *args, size_t nargs,
	struct Object **result)
{
	return f->cfunc(interp, f->userdata, args, nargs, result);
}

static void destroy_func(struct Object *obj, bool decrefrefs, bool freenonrefs)
{
	struct FuncObject *f = (struct FuncObject *)obj;
	if (f->userdata.destroy)
		f->userdata.destroy(f->userdata.val, decrefrefs, freenonrefs);
}

struct FuncObject *funcobj_new(Interp *interp, funcobj_cfunc cfunc, struct ObjData userdata)
{
	struct FuncObject *f = object_new(interp, &funcobj_type, destroy_func, sizeof(*f));
	if (!f) {
		if(userdata.destroy) userdata.destroy(userdata.val, true, true);
		return NULL;
	}

	f->userdata = userdata;
	f->cfunc = cfunc;
	return f;
}
