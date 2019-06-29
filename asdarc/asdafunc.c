#include "asdafunc.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "objtyp.h"
#include "runner.h"
#include "objects/func.h"
#include "objects/scope.h"

struct AsdaFunctionData {
	struct Object *defscope;
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

static enum RunnerResult run(struct Interp *interp, const struct AsdaFunctionData *afd, struct Runner *rnr, struct Object **args, size_t nargs)
{
	struct Object *sco = scopeobj_newsub(interp, afd->defscope, afd->code.nlocalvars);
	if(!sco)
		return RUNNER_ERROR;

	assert(nargs <= afd->code.nlocalvars);
	memcpy(scopeobj_getlocalvarsptr(sco), args, sizeof(args[0]) * nargs);
	for (size_t i = 0; i < nargs; i++)
		OBJECT_INCREF(args[i]);

	runner_init(rnr, interp, sco, afd->code);
	OBJECT_DECREF(sco);

	enum RunnerResult res = runner_run(rnr);
	runner_free(rnr);
	return res;
}

static struct Object *asda_function_cfunc_ret(struct Interp *interp, struct ObjData data, struct Object **args, size_t nargs)
{
	struct Runner rnr;
	switch (run(interp, data.val, &rnr, args, nargs)) {
	// compiler adds a didn't return error to end of returning functions, so RUNNER_DIDNTRETURN can't happen here
	case RUNNER_ERROR:
		return NULL;
	case RUNNER_VALUERETURN:
		return rnr.retval;
	default:
		assert(0);
	}
}

static bool asda_function_cfunc_noret(struct Interp *interp, struct ObjData data, struct Object **args, size_t nargs)
{
	struct Runner rnr;
	switch (run(interp, data.val, &rnr, args, nargs)) {
	// compiler adds a void return to end of non-returning functions, so RUNNER_DIDNTRETURN can't happen here
	case RUNNER_ERROR:
		return false;
	case RUNNER_VOIDRETURN:
		return true;
	default:
		assert(0);
	}
}

struct Object *asdafunc_create(struct Interp *interp, struct Object *defscope, struct Code code, bool ret)
{
	struct AsdaFunctionData *afd = malloc(sizeof(*afd));
	if(!afd) {
		interp_errstr_nomem(interp);
		return NULL;
	}

	afd->defscope = defscope;
	OBJECT_INCREF(defscope);
	afd->code = code;

	struct ObjData od = { .val = afd, .destroy = destroy_asdafunc_data };
	if(ret)
		return funcobj_new_ret(interp, asda_function_cfunc_ret, od);
	else
		return funcobj_new_noret(interp, asda_function_cfunc_noret, od);
}
