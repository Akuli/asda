#include "asdafunc.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "objtyp.h"
#include "runner.h"
#include "objects/func.h"
#include "objects/scope.h"

struct AsdaFunctionData {
	struct Object *defscope;
	struct Bc bc;
};

static void destroy_asdafunctiondata(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	// bc is not destroyed, reason explained in asdafunc.h
	if(decrefrefs)
		OBJECT_DECREF( ((struct AsdaFunctionData*)vpdata)->defscope );
	if(freenonrefs)
		free(vpdata);
}

static bool asda_function_cfunc(struct Interp *interp, struct ObjData data, struct Object **args, size_t nargs)
{
	struct AsdaFunctionData *afd = data.val;

	struct Object *scope = scopeobj_newsub(interp, afd->defscope, afd->bc.nlocalvars);
	if(!scope)
		return false;

	struct Runner rnr;
	runner_init(&rnr, interp, scope, afd->bc);
	OBJECT_DECREF(scope);

	enum RunnerResult res = runner_run(&rnr);
	runner_free(&rnr);

	switch(res) {
	case RUNNER_VOIDRETURN:
	case RUNNER_DIDNTRETURN:
		return true;
	case RUNNER_ERROR:
		return false;
	default:
		assert(0);    // bug in asda compiler or something not implemented in this interpreter
	}
}

struct Object *asdafunc_create_noret(struct Interp *interp, struct Object *defscope, struct Bc bc)
{
	struct AsdaFunctionData *afd = malloc(sizeof(*afd));
	if(!afd) {
		interp_errstr_nomem(interp);
		return NULL;
	}

	afd->defscope = defscope;
	OBJECT_INCREF(defscope);
	afd->bc = bc;

	return funcobj_new_noret(interp, asda_function_cfunc, (struct ObjData){
		.val = afd,
		.destroy = destroy_asdafunctiondata,
	});
}
