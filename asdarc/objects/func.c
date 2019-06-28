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
		if(!( allargs = malloc((fod->npartial + nargs) * sizeof(allargs[0])) ))
			return res;
		memcpy(allargs, fod->partial, fod->npartial * sizeof(allargs[0]));
		memcpy(allargs+fod->npartial, args, nargs * sizeof(allargs[0]));
	}

	if(ret)
		res.ret = fod->cfunc.ret(interp, allargs, fod->npartial + nargs);
	else
		res.noret = fod->cfunc.noret(interp, allargs, fod->npartial + nargs);

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

	if(decrefrefs) {
		for (struct Object **ptr = data->partial; ptr < data->partial+data->npartial; ptr++)
			OBJECT_DECREF(*ptr);
	}
	if (freenonrefs) {
		free(data->partial);
		free(data);
	}
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
