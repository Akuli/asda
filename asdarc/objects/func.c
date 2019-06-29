#include "func.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "../interp.h"
#include "../objtyp.h"


const struct Type funcobj_type_ret = {
	.methods = NULL,
	.nmethods = 0,
};
const struct Type funcobj_type_noret = {
	.methods = NULL,
	.nmethods = 0,
};


union call_result {
	struct Object *ret;
	bool noret;
};

static union call_result call(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs, bool ret)
{
	union call_result res;
	if(ret) {
		assert(f->type == &funcobj_type_ret);
		res.ret = NULL;
	} else {
		assert(f->type == &funcobj_type_noret);
		res.noret = false;
	}

	struct FuncObjData *fod = f->data.val;

	struct Object **allargs;
	if (fod->npartial == 0) {
		allargs = args;
	} else {
		if(!( allargs = malloc((fod->npartial + nargs) * sizeof(allargs[0])) )) {
			interp_errstr_nomem(interp);
			return res;
		}
		memcpy(allargs, fod->partial, fod->npartial * sizeof(allargs[0]));
		memcpy(allargs+fod->npartial, args, nargs * sizeof(allargs[0]));
	}

	if(ret)
		res.ret = fod->cfunc.ret(interp, fod->data, allargs, fod->npartial + nargs);
	else
		res.noret = fod->cfunc.noret(interp, fod->data, allargs, fod->npartial + nargs);

	if(fod->npartial != 0)
		free(allargs);
	return res;
}

bool funcobj_call_noret(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs)
{
	return call(interp, f, args, nargs, false).noret;
}

struct Object *funcobj_call_ret(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs)
{
	return call(interp, f, args, nargs, true).ret;
}


static void funcdata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct FuncObjData *data = vpdata;

	if (data->data.destroy)
		data->data.destroy(data->data.val, decrefrefs, freenonrefs);

	if(decrefrefs) {
		for (struct Object **ptr = data->partial; ptr < data->partial+data->npartial; ptr++)
			OBJECT_DECREF(*ptr);
	}
	if (freenonrefs) {
		free(data->partial);
		free(data);
	}
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

struct Object *funcobj_new_noret(struct Interp *interp, funcobj_cfunc_noret f, struct ObjData data)
{
	struct FuncObjData fod = FUNCOBJDATA_COMPILETIMECREATE_NORET(f);
	fod.data = data;
	return new_function(interp, fod, &funcobj_type_noret);
}

struct Object *funcobj_new_ret(struct Interp *interp, funcobj_cfunc_ret f, struct ObjData data)
{
	struct FuncObjData fod = FUNCOBJDATA_COMPILETIMECREATE_RET(f);
	fod.data = data;
	return new_function(interp, fod, &funcobj_type_ret);
}


struct Object *funcobj_new_partial(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs)
{
	assert(f->type == &funcobj_type_ret || f->type == &funcobj_type_noret);

	// this guarantees that code below doesn't do malloc(0)
	if(nargs == 0) {
		OBJECT_INCREF(f);
		return f;
	}

	struct FuncObjData *data = f->data.val;

	struct FuncObjData *newdata = malloc(sizeof(*newdata));
	struct Object **newpartial = malloc((data->npartial + nargs) * sizeof(struct Object*));
	if(!newdata || !newpartial) {
		free(newdata);
		free(newpartial);
		interp_errstr_nomem(interp);
		return NULL;
	}

	newdata->data = data->data;
	newdata->data.destroy = NULL;    // FIXME: this is brokene hack

	memcpy(newpartial, data->partial, data->npartial * sizeof(struct Object*));
	memcpy(newpartial+data->npartial, args, nargs * sizeof(struct Object*));

	for (struct Object **ptr = newpartial; ptr < newpartial+(data->npartial + nargs); ptr++)
		OBJECT_INCREF(*ptr);

	newdata->cfunc = data->cfunc;
	newdata->partial = newpartial;
	newdata->npartial = data->npartial + nargs;
	return object_new(interp, f->type, (struct ObjData){
		.val = newdata,
		.destroy = funcdata_destroy,
	});
}
