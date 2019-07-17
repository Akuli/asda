#ifndef RUNNER_H
#define RUNNER_H

#include <stddef.h>
#include "dynarray.h"
#include "code.h"
#include "interp.h"
#include "objtyp.h"
#include "objects/err.h"
#include "objects/scope.h"

// see finally.md
// don't use this outside runner.c
struct RunnerFinallyState {
	enum CodeOpKind kind;   // one of CODE_FS_* things, but not CODE_FS_APPLY or CODE_FS_DISCARD
	union {
		Object *obj;       // error or return value, for CODE_FS_VALUERETURN and CODE_FS_ERROR
		size_t jumpidx;    // for CODE_FS_JUMP
	} val;
};

struct Runner {
	Object *retval;

	// don't access rest of these directly
	Interp *interp;
	ScopeObject *scope;
	DynArray(Object*) stack;
	DynArray(struct CodeErrHndData) ehstack;        // see finally.md
	DynArray(struct RunnerFinallyState) fsstack;    // see finally.md
	size_t opidx;
	struct Code code;
};

// never fails
// increfs the scope as needed
// never frees the bc
void runner_init(struct Runner *rnr, Interp *interp, ScopeObject *scope, struct Code code);

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
