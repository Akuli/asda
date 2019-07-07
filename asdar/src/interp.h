#ifndef INTERP_H
#define INTERP_H

// errno is used in the macros, iwyu doesn't know that
#include <errno.h>   // IWYU pragma: keep
#include <stdbool.h>

// forward declarations needed because many things need an Interp
struct ObjectStruct;
struct Module;

typedef struct InterpStruct {
	const char *argv0;
	struct ObjectStruct *builtinscope;

	// the only object created at runtime that has ->prev == NULL
	// all (not yet destroyed) runtime created objects can be found from here with ->next
	struct ObjectStruct *objliststart;

	// see objects/err.h
	struct ObjectStruct *err;

	// don't access this directly, use functions in module.h instead
	struct Module *firstmod;

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

	This is an absolute path and it's set in main.c
	*/
	const char *basedir;
} Interp;

// returns false and sets an error to interp->err on no mem
bool interp_init(Interp *interp, const char *argv0);

// never fails, always leaves errstr untouched
void interp_destroy(Interp *interp);

#endif   // INTERP_H
