#ifndef RUNNER_H
#define RUNNER_H

#include <stddef.h>
#include "dynarray.h"
#include "code.h"
#include "interp.h"
#include "objtyp.h"

// think of the content of this struct as an implementation detail
struct Runner {
	Interp *interp;
	Object *scope;
	DynArray(Object*) stack;
	size_t opidx;
	struct Code code;
	Object *retval;  // returned value, NOT an implementation detail unlike everything else
};

// never fails
// increfs the scope as needed
// never frees the bc
void runner_init(struct Runner *rnr, Interp *interp, Object *scope, struct Code code);

// never fails
void runner_free(const struct Runner *rnr);

enum RunnerResult {
	RUNNER_VOIDRETURN,
	RUNNER_VALUERETURN,
	RUNNER_DIDNTRETURN,
	RUNNER_ERROR,
};

// must not be called multiple times
// if returns RUNNER_VALUERETURN, caller may use rnr->retval and must decref it eventually
enum RunnerResult runner_run(struct Runner *rnr);


#endif   // RUNNER_H
