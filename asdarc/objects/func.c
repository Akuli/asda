#include "func.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "../interp.h"
#include "../objtyp.h"


const struct Type funcobj_type_ret   = { .methods = NULL, .nmethods = 0 };
const struct Type funcobj_type_noret = { .methods = NULL, .nmethods = 0 };


Object *funcobj_call_ret(Interp *interp, Object *f, Object *const *args, size_t nargs)
{
	assert(f->type == &funcobj_type_ret);
	struct FuncObjData *fod = f->data.val;
	return fod->cfunc.ret(interp, fod->data, args, nargs);
}

bool funcobj_call_noret(Interp *interp, Object *f, Object *const *args, size_t nargs)
{
	assert(f->type == &funcobj_type_noret);
	struct FuncObjData *fod = f->data.val;
	return fod->cfunc.noret(interp, fod->data, args, nargs);
}


static void funcdata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct FuncObjData *data = vpdata;

	if (data->data.destroy)
		data->data.destroy(data->data.val, decrefrefs, freenonrefs);

	if (freenonrefs)
		free(data);
}


static Object *new_function(Interp *interp, struct FuncObjData fod, const struct Type *typ)
{
	struct FuncObjData *fodp = malloc(sizeof(*fodp));
	if(!fodp) {
		interp_errstr_nomem(interp);
		if(fod.data.destroy)
			fod.data.destroy(fod.data.val, true, true);
		return NULL;
	}

	*fodp = fod;
	return object_new(interp, typ, (struct ObjData){
		.val = fodp,
		.destroy = funcdata_destroy,
	});
}

Object *funcobj_new_ret(Interp *interp, funcobj_cfunc_ret f, struct ObjData data)
{
	struct FuncObjData fod = FUNCOBJDATA_COMPILETIMECREATE_RET(f);
	fod.data = data;
	return new_function(interp, fod, &funcobj_type_ret);
}

Object *funcobj_new_noret(Interp *interp, funcobj_cfunc_noret f, struct ObjData data)
{
	struct FuncObjData fod = FUNCOBJDATA_COMPILETIMECREATE_NORET(f);
	fod.data = data;
	return new_function(interp, fod, &funcobj_type_noret);
}
