#include "func.h"
#include <stdbool.h>
#include "../interp.h"
#include "../objtyp.h"

const struct Type funcobj_type = { .methods = NULL, .nmethods = 0 };

bool funcobj_call(Interp *interp, FuncObject *f, Object *const *args, size_t nargs, Object **result)
{
	return f->cfunc(interp, f->userdata, args, nargs, result);
}

static void destroy_func(Object *obj, bool decrefrefs, bool freenonrefs)
{
	FuncObject *f = (FuncObject *)obj;
	if (f->userdata.destroy)
		f->userdata.destroy(f->userdata.val, decrefrefs, freenonrefs);
}

FuncObject *funcobj_new(Interp *interp, funcobj_cfunc cfunc, struct ObjData userdata)
{
	FuncObject *f = object_new(interp, &funcobj_type, destroy_func, sizeof(*f));
	if (!f) {
		if(userdata.destroy) userdata.destroy(userdata.val, true, true);
		return NULL;
	}

	f->userdata = userdata;
	f->cfunc = cfunc;
	return f;
}
