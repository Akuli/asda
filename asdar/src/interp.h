#ifndef INTERP_H
#define INTERP_H

#include "dynarray.h"

// forward declarations needed because many things need an Interp
struct CodeOp;
struct Object;
struct ErrObject;
struct IntObject;

/*
Call stacks are not attached to error objects because the same error object may
get thrown twice, and in that case it should have different call stacks. This
struct is an error object and the call stack leading to the line that threw up.
*/
struct InterpErrStackItem {
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

typedef struct Interp {
	const char *argv0;

	// Start of linked list of all runtime-created objects
	struct Object *objliststart;

	/*
	paths of imported modules are treated relative to this

	This path is needed for case (in)sensitivity reasons.
	For example, let's say that foo.asda imports subdir/bar.asda.
	Then running asda-compiled/foo.asdac from /BlahBlah/ would import these paths:

		/BlahBlah/asda-compiled/foo.asdac
		/BlahBlah/asda-compiled/subdir/bar.asdac

	There is no good way to detect whether a path should be treated case-sensitive or case-insensitive.
	The compiler lowercases paths of all compiled files.
	To compare these paths correctly, the basedir defined here would be set to '/BlahBlah'.
	Then the path of modules would be 'foo.asdac' and 'subdir/bar.asdac'.
	Those are guaranteed to be lowercase and therefore are easy to compare with each other.

	This is an absolute path and it's set in main.c, but interp_init() sets it to NULL temporarily
	*/
	const char *basedir;

	// optimization for Int objects, contains integers 0, 1, 2, ...
	struct IntObject* intcache[20];

	// pointers into the code dynarray
	// assumes that interp->code.ptr isn't reallocated while running, e.g. nothing imported while running
	// runner.c adds an item to this when functions are ran
	// items from this are displayed in error messages (aka stack traces)
	DynArray(const struct CodeOp *) callstack;

	// this is for local variables and arguments
	DynArray(struct Object *) objstack;

	/*
	The purpose of this is that when an error happens while handling another
	error, both errors are shown in the error message. For example, let's say
	that error1 happens. Then while handling that, we get error2, and while
	handling error2 we get error3. Then all the errors go to errstack, and the
	error message printing code finds them from there.
	*/
	DynArray(struct InterpErrStackItem) errstack;

	// code being ran, from all imported modules
	DynArray(struct CodeOp) code;
} Interp;


// may fail for no memory, then this returns false
bool interp_init(Interp *interp, const char *argv0);

// never fails
void interp_destroy(Interp *interp);

#endif   // INTERP_H
