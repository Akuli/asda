#ifndef STACKTRACE_H
#define STACKTRACE_H

#include <stddef.h>
#include "code.h"
#include "objects/err.h"

/*
Call stacks are not attached to error objects because the same error object may
get thrown twice, and in that case it should have different call stacks. This
struct is an error object and the call stack leading to the line that threw up.
*/
struct StackTrace {
	struct ErrObject *errobj;

	// what were we doing when we got error?
	const struct CodeOp *op;

	/*
	If the callstack is too long for this, then we ignore some of it in the
	middle. Generally the start and end of long stack traces are worth looking at,
	and the middle of a stack trace is often uninteresting.

	Having to allocate these when starting error handling could mean that we fail
	to handle an error without being able to print a stack trace, which is what we
	really want to avoid the most. This means that we need to allocate space for
	the callstack associated with each error before the error actually happens,
	and we don't know yet how much space we need.
	*/
	const struct CodeOp *callstack[200];
	size_t callstacklen;
	size_t callstackskip;   // how many items missing from middle of callstack
};

/*
doesn't care much about IO errors, because ... well, what would you do to them?
print another stack trace that also gets lost and cause infinite loop?
*/
void stacktrace_print(Interp *interp, const struct StackTrace *st);

/*
Early on interpreter startup, no asda code has ran yet so we don't have stack
traces. It's still possible to get errors.
*/
void stacktrace_print_raw(ErrObject *err);


#endif    // STACKTRACE_H
