#ifndef RUNNER_H
#define RUNNER_H

#include <stdbool.h>
#include <stddef.h>
#include "bc.h"
#include "interp.h"
#include "objtyp.h"

enum RunResult {
	DIDNT_RETURN,
};

struct Runner {
	struct Interp *interp;
	struct Object *scope;
	struct Object **stack;
	size_t stacklen, stacksz;
};

// never fails
void runner_init(struct Runner *rnr, struct Interp *interp, struct Object *scope);
void runner_free(const struct Runner *rnr);

bool runner_run(struct Runner *rnr, struct Bc bc);


#endif   // RUNNER_H
