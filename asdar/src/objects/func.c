#include "func.h"
#include <stdbool.h>
#include "../interp.h"
#include "../object.h"
#include "../type.h"

bool funcobj_call(Interp *interp, FuncObject *f, Object *const *args, size_t nargs, Object **result)
{
	// uncomment to debug
	//assert(nargs == ((const struct TypeFunc *) f->type)->nargtypes);
	return f->cfunc(interp, f->userdata, args, nargs, result);
}

static void destroy_func(Object *obj, bool decrefrefs, bool freenonrefs)
{
	FuncObject *f = (FuncObject *)obj;
	if (f->userdata.destroy)
		f->userdata.destroy(f->userdata.val, decrefrefs, freenonrefs);
}

FuncObject *funcobj_new(Interp *interp, const struct TypeFunc *type, funcobj_cfunc cfunc, struct ObjData userdata)
{
	FuncObject *f = object_new(interp, (const struct Type *)type, destroy_func, sizeof(*f));
	if (!f) {
		if(userdata.destroy) userdata.destroy(userdata.val, true, true);
		return NULL;
	}

	f->userdata = userdata;
	f->cfunc = cfunc;
	return f;
}
