#ifndef MODULE_H
#define MODULE_H

#include "code.h"
#include "objtyp.h"

struct Module {
	// case (in)sensitivity handling for the path:
	// compiler makes all output file paths relative and lower case
	// all paths are loaded by joining them to an absoloute path of what is passed as an argument to the interpreter
	// the path declared here is absolute

	char *path;         // path of the compiled bytecode file, not the source file
	Object *scope;      // a subscope of the built-in scope
	struct Code code;   // loaded from the path

	// binary search tree for looking up modules by path quickly
	// don't rely on these outside module.c
	struct Module *left;
	struct Module *right;
};

// returns NULL if there is no module with the given path yet (that is NOT an error! this never errors)
const struct Module *module_get(Interp *interp, const char *path);

// mod should be allocated with malloc() and have everything except ->left and ->right set
// this cannot fail, but this asserts that a module with the same name doesn't exist
// these will be done eventually:
//   - mod->scope will be decreffed
//   - mod->code will be destroyed
//   - mod->path will be freed
//   - mod will be freed
void module_add(Interp *interp, struct Module *mod);

// called on interpreter exit
void module_destroyall(Interp *interp);

#endif  // MODULE_H
