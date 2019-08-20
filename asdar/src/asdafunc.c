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

static enum RunnerResult
run(Interp *interp, const struct Code *code, struct Runner *rnr, Object *const *args, size_t nargs)
{
	if (!runner_init(rnr, interp, code))
		return RUNNER_ERROR;

	assert(nargs <= code->maxstacksz);
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

FuncObject *asdafunc_create(Interp *interp, const struct TypeFunc *type, const struct Code *code)
{
	// BE CAREFUL to not modify the code in the rest of this file
	// od.val is non-const void* pointer but code is const pointer
	// this is simpler than wrapping the code inside a one-element struct
	struct ObjData od = { .val = (void *)code, .destroy = NULL };
	return funcobj_new(interp, type, asda_function_cfunc, od);
}
