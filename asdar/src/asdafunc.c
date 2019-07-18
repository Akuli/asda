#include "asdafunc.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "code.h"
#include "interp.h"
#include "objtyp.h"
#include "runner.h"
#include "objects/err.h"
#include "objects/func.h"
#include "objects/scope.h"

struct AsdaFunctionData {
	ScopeObject *defscope;
	struct Code code;
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
	ScopeObject *sco = scopeobj_newsub(interp, afd->defscope, afd->code.nlocalvars);
	if(!sco)
		return RUNNER_ERROR;

	assert(nargs <= afd->code.nlocalvars);
	memcpy(sco->locals, args, sizeof(args[0]) * nargs);
	for (size_t i = 0; i < nargs; i++)
		OBJECT_INCREF(args[i]);

	runner_init(rnr, interp, sco, afd->code);
	OBJECT_DECREF(sco);

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

		case RUNNER_VOIDRETURN:
			*result = NULL;
			return true;

		case RUNNER_ERROR:
			return false;

		case RUNNER_DIDNTRETURN:
			// compiler adds a didn't return error to end of returning functions
			assert(0);
	}

	// never runs, silences compiler warning
	assert(0);
	return false;
}

FuncObject *asdafunc_create(Interp *interp, ScopeObject *defscope, struct Code code)
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
	return funcobj_new(interp, asda_function_cfunc, od);
}
