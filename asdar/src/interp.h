#ifndef INTERP_H
#define INTERP_H

#include "code.h"
#include "dynarray.h"

// forward declarations needed because many things need an Interp
struct Object;
struct ErrObject;
struct IntObject;

struct InterpModInfo {
	char *srcpathabs;
	char *bcpathabs;
	char *bcpathrel;   // relative to interp->basedir

	// index into interp->code
	size_t startidx;
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

	// when an error occurs, it goes here and then run.h may pick it up from here
	struct ErrObject *err;

	// code being ran, from all imported modules
	DynArray(struct CodeOp) code;

	// info about imported modules
	DynArray(struct InterpModInfo) mods;

	/*
	functions written in c, sorted by name.

	Why this data structure out of all the possible choices? Because then finding
	something from this while reading bytecode will be quick even though this is
	not that difficult to implement.

	Some day there may be a way to put c functions into asda libraries, and if
	shifting the items of this array turns out to be too slow, then I can change
	this. I don't think it will be that slow.
	*/
	DynArray(const struct CFunc *) cfuncs;
} Interp;


// never fails
void interp_init(Interp *interp, const char *argv0);

// never fails
void interp_destroy(Interp *interp);

#endif   // INTERP_H
