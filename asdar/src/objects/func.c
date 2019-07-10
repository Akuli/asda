#include "func.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "../interp.h"
#include "../objtyp.h"
#include "err.h"

const struct Type funcobj_type = { .methods = NULL, .nmethods = 0 };

bool funcobj_call(Interp *interp, Object *f, Object *const *args, size_t nargs, Object **result)
{
	assert(f->type == &funcobj_type);
	struct FuncObjData *data = f->data.val;
	return data->cfunc(interp, data->userdata, args, nargs, result);
}

static void funcdata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct FuncObjData *data = vpdata;

	if (data->userdata.destroy) data->userdata.destroy(data->userdata.val, decrefrefs, freenonrefs);

	if (freenonrefs) free(data);
}

Object *funcobj_new(Interp *interp, funcobj_cfunc cfunc, struct ObjData userdata)
{
	struct FuncObjData *data = malloc(sizeof *data);
	if(!data) {
		errobj_set_nomem(interp);
		if(userdata.destroy) userdata.destroy(userdata.val, true, true);
		return NULL;
	}
	data->userdata = userdata;
	data->cfunc = cfunc;

	return object_new(interp, &funcobj_type, (struct ObjData){
		.val = data,
		.destroy = funcdata_destroy,
	});
}
