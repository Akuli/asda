#ifndef RUNNER_H
#define RUNNER_H

#include <stddef.h>
#include "dynarray.h"
#include "code.h"
#include "interp.h"
#include "object.h"

// don't use this outside runner.c
struct RunnerFinallyState;

struct Runner {
	Object *retval;
	Object **stackbot;
	Object **stacktop;

	// don't access rest of these directly
	Interp *interp;
	DynArray(struct CodeErrHnd) ehstack;            // see finally.md
	DynArray(struct RunnerFinallyState) fsstack;    // see finally.md
	size_t opidx;
	const struct Code *code;
};

// increfs the scope as needed
// never frees the bc
// don't call runner_free when this fails
bool runner_init(struct Runner *rnr, Interp *interp, const struct Code *code);

// never fails
void runner_free(const struct Runner *rnr);

enum RunnerResult {
	RUNNER_VALUERETURN,
	RUNNER_DIDNTRETURN,   // also represents returning from '-> void' function
	RUNNER_ERROR,
};

// must not be called multiple times
// if returns RUNNER_VALUERETURN, caller may use rnr->retval and must decref it eventually
enum RunnerResult runner_run(struct Runner *rnr);


#endif   // RUNNER_H
