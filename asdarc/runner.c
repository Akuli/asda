#include "runner.h"
#include <stdlib.h>
#include <string.h>
#include "interp.h"


void runner_init(struct Runner *rnr, struct Interp *interp, struct Object *scope)
{
	rnr->interp = interp;
	rnr->stack = NULL;
	rnr->stacklen = 0;
	rnr->stacksz = 0;
}

void runner_free(struct Runner *rnr)
{
	for (struct Object **ptr = rnr->stack; ptr < rnr->stack + rnr->stacklen; ptr++)
		if (*ptr)
			OBJECT_DECREF(*ptr);
	free(rnr->stack);
}

static bool grow_stack(struct Runner *rnr, size_t minsz)
{
	if (rnr->stacksz >= minsz)
		return true;

	size_t newsz;

	// I haven't changing the hard-coded constants to optimize
	if (rnr->stacksz == 0)
		newsz = 3;
	else
		newsz = 2 * rnr->stacksz;

	if (newsz < minsz)
		newsz = minsz;

	if (!( rnr->stack = realloc(rnr->stack, sizeof(struct Object*) * newsz) )) {
		interp_errstr_nomem(rnr->interp);
		return false;
	}

	rnr->stacksz = newsz;
	return true;
}

static bool push2stack(struct Runner *rnr, struct Object *obj)
{
	if (!grow_stack(rnr, rnr->stacklen+1))
		return false;
	rnr->stack[rnr->stacklen++] = obj;
	OBJECT_INCREF(obj);
	return true;
}
