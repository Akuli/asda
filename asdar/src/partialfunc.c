#include "partialfunc.h"
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "interp.h"
#include "objtyp.h"
#include "objects/err.h"
#include "objects/func.h"

struct PartialFuncData {
	struct FuncObject *f;
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

static bool
call_partial_func(Interp *interp, struct ObjData data, struct Object *const *args, size_t nargs, struct Object **result)
{
	const struct PartialFuncData *pfd = data.val;

	struct Object **allargs;
	if (nargs == 0) {
		allargs = pfd->partial;
	} else {
		// this doesn't do malloc(0)
		if(!( allargs = malloc((pfd->npartial + nargs) * sizeof(allargs[0])) )) {
			errobj_set_nomem(interp);
			return false;
		}
		memcpy(allargs, pfd->partial, pfd->npartial * sizeof(allargs[0]));
		memcpy(allargs+pfd->npartial, args, nargs * sizeof(allargs[0]));
	}

	bool ok = funcobj_call(interp, pfd->f, allargs, pfd->npartial + nargs, result);
	if (nargs != 0) free(allargs);
	return ok;
}

static bool partialfunc_cfunc(Interp *interp, struct ObjData data, struct Object *const *args, size_t nargs, struct Object **result)
{
	return call_partial_func(interp, data, args, nargs, result);
}

struct FuncObject *
partialfunc_create(Interp *interp, struct FuncObject *f, struct Object *const *partial, size_t npartial)
{
	if (npartial == 0) {
		OBJECT_INCREF(f);
		return f;
	}

	struct PartialFuncData *pfd = malloc(sizeof(*pfd));
	struct Object **partialcp = malloc(sizeof(partial[0]) * npartial);
	if(!partialcp || !pfd) {
		errobj_set_nomem(interp);
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
	return funcobj_new(interp, partialfunc_cfunc, od);
}
