#ifndef RUNNER_H
#define RUNNER_H

#include "interp.h"

enum RunResult {
	DIDNT_RETURN,
};

struct Runner {
	struct Interp *interp;
	struct Object **stack;
	size_t stacklen, stacksz;
};

// never fails
void runner_init(struct Runner *rnr, struct Interp *interp, struct Object *scope);
void runner_free(struct Runner *rnr);

#endif   // RUNNER_H
