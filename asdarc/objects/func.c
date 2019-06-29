#include "func.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../interp.h"
#include "../objtyp.h"


const struct Type funcobj_type_ret   = { .methods = NULL, .nmethods = 0 };
const struct Type funcobj_type_noret = { .methods = NULL, .nmethods = 0 };


struct Object *funcobj_call_ret(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs)
{
	assert(f->type == &funcobj_type_ret);
	struct FuncObjData *fod = f->data.val;
	return fod->cfunc.ret(interp, fod->data, args, nargs);
}

bool funcobj_call_noret(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs)
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


static struct Object *new_function(struct Interp *interp, struct FuncObjData fod, const struct Type *typ)
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

struct Object *funcobj_new_ret(struct Interp *interp, funcobj_cfunc_ret f, struct ObjData data)
{
	struct FuncObjData fod = FUNCOBJDATA_COMPILETIMECREATE_RET(f);
	fod.data = data;
	return new_function(interp, fod, &funcobj_type_ret);
}

struct Object *funcobj_new_noret(struct Interp *interp, funcobj_cfunc_noret f, struct ObjData data)
{
	struct FuncObjData fod = FUNCOBJDATA_COMPILETIMECREATE_NORET(f);
	fod.data = data;
	return new_function(interp, fod, &funcobj_type_noret);
}
