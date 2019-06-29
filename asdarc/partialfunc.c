#include "partialfunc.h"
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "interp.h"
#include "objtyp.h"
#include "objects/func.h"

struct PartialFuncData {
	struct Object *f;
	struct Object **partial;
	size_t npartial;
};

static void partialfunc_data_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct PartialFuncData *pfd = vpdata;
	if (decrefrefs) {
		OBJECT_DECREF(pfd->f);
		for (size_t i = 0; i < pfd->npartial; i++)
			OBJECT_DECREF(pfd->partial[i]);
	}
	if (freenonrefs) {
		free(pfd->partial);
		free(pfd);
	}
}

union call_result {
	struct Object *ret;
	bool noret;
};

static union call_result
call_partial_func(struct Interp *interp, struct ObjData data, struct Object *const *args, size_t nargs, bool ret)
{
	const struct PartialFuncData *pfd = data.val;

	union call_result res;
	if(ret) {
		assert(pfd->f->type == &funcobj_type_ret);
		res.ret = NULL;
	} else {
		assert(pfd->f->type == &funcobj_type_noret);
		res.noret = false;
	}

	struct Object **allargs;
	if (nargs == 0)
		allargs = pfd->partial;
	else {
		// this doesn't do malloc(0)
		if(!( allargs = malloc((pfd->npartial + nargs) * sizeof(allargs[0])) )) {
			interp_errstr_nomem(interp);
			return res;
		}
		memcpy(allargs, pfd->partial, pfd->npartial * sizeof(allargs[0]));
		memcpy(allargs+pfd->npartial, args, nargs * sizeof(allargs[0]));
	}

	if(ret)
		res.ret = funcobj_call_ret(interp, pfd->f, allargs, pfd->npartial + nargs);
	else
		res.noret = funcobj_call_noret(interp, pfd->f, allargs, pfd->npartial + nargs);

	if (nargs != 0)
		free(allargs);
	return res;
}

struct Object *partialfunc_cfunc_ret(struct Interp *interp, struct ObjData data, struct Object *const *args, size_t nargs)
{
	return call_partial_func(interp, data, args, nargs, true).ret;
}

bool partialfunc_cfunc_noret(struct Interp *interp, struct ObjData data, struct Object *const *args, size_t nargs)
{
	return call_partial_func(interp, data, args, nargs, false).noret;
}


struct Object *
partialfunc_create(struct Interp *interp, struct Object *f, struct Object *const *partial, size_t npartial)
{
	if (npartial == 0) {
		OBJECT_INCREF(f);
		return f;
	}

	struct PartialFuncData *pfd = malloc(sizeof(*pfd));
	struct Object **partialcp = malloc(sizeof(partial[0]) * npartial);
	if(!partialcp || !pfd) {
		interp_errstr_nomem(interp);
		return NULL;
	}

	pfd->partial = partialcp;
	pfd->npartial = npartial;
	pfd->f = f;
	OBJECT_INCREF(f);

	memcpy(partialcp, partial, sizeof(partial[0]) * npartial);
	for (size_t i = 0; i < npartial; i++)
		OBJECT_INCREF(partialcp[i]);

	struct ObjData od = { .val = pfd, .destroy = partialfunc_data_destroy };

	if (f->type == &funcobj_type_ret)
		return funcobj_new_ret(interp, partialfunc_cfunc_ret, od);
	if (f->type == &funcobj_type_noret)
		return funcobj_new_noret(interp, partialfunc_cfunc_noret, od);
	assert(0);
}
