#ifndef RUNNER_H
#define RUNNER_H

#include <stdbool.h>
#include <stddef.h>
#include "bc.h"
#include "interp.h"
#include "objtyp.h"

// think of the content of this struct as an implementation detail
struct Runner {
	struct Interp *interp;
	struct Object *scope;
	struct Object **stack;
	size_t stacklen, stacksz;
	size_t opidx;
	struct Bc bc;
	struct Object *retval;  // returned value, NOT an implementation detail unlike everything else
};

// never fails
// increfs the scope as needed
// never frees the bc
void runner_init(struct Runner *rnr, struct Interp *interp, struct Object *scope, struct Bc bc);

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
