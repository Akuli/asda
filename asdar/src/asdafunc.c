#include "asdafunc.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "code.h"
#include "interp.h"
#include "object.h"
#include "runner.h"
#include "type.h"
#include "objects/err.h"
#include "objects/func.h"
#include "objects/scope.h"

struct AsdaFunctionData {
	ScopeObject *defscope;
	const struct Code *code;
};

static void destroy_asdafunc_data(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	// code is not destroyed, reason explained in asdafunc.h
	if(decrefrefs)
		OBJECT_DECREF( ((struct AsdaFunctionData*)vpdata)->defscope );
	if(freenonrefs)
		free(vpdata);
}

static enum RunnerResult
run(Interp *interp, const struct AsdaFunctionData *afd, struct Runner *rnr, Object *const *args, size_t nargs)
{
	ScopeObject *sco = scopeobj_newsub(interp, afd->defscope, afd->code->nlocalvars);
	if(!sco)
		return RUNNER_ERROR;

	bool ok = runner_init(rnr, interp, sco, afd->code);
	OBJECT_DECREF(sco);
	if (!ok)
		return RUNNER_ERROR;

	assert(nargs <= afd->code->maxstacksz);
	assert(rnr->stacktop == rnr->stackbot);

	memcpy(rnr->stackbot, args, sizeof(args[0]) * nargs);
	rnr->stacktop += nargs;
	for (size_t i = 0; i < nargs; i++)
		OBJECT_INCREF(args[i]);

	enum RunnerResult res = runner_run(rnr);
	runner_free(rnr);
	return res;
}

static bool asda_function_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	struct Runner rnr;

	switch (run(interp, data.val, &rnr, args, nargs)) {
		case RUNNER_VALUERETURN:
			*result = rnr.retval;
			return true;

		case RUNNER_DIDNTRETURN:
			*result = NULL;
			return true;

		case RUNNER_ERROR:
			return false;
	}

	// never runs, silences compiler warning
	assert(0);
	return false;
}

FuncObject *asdafunc_create(Interp *interp, ScopeObject *defscope, const struct TypeFunc *type, const struct Code *code)
{
	struct AsdaFunctionData *afd = malloc(sizeof(*afd));
	if(!afd) {
		errobj_set_nomem(interp);
		return NULL;
	}

	afd->defscope = defscope;
	OBJECT_INCREF(defscope);
	afd->code = code;

	struct ObjData od = { .val = afd, .destroy = destroy_asdafunc_data };
	return funcobj_new(interp, type, asda_function_cfunc, od);
}
