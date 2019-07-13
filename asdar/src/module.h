#ifndef MODULE_H
#define MODULE_H

#include "code.h"
#include "interp.h"
#include "objtyp.h"
#include "objects/scope.h"

struct Module {
	// see interp->basedir comments for more details about the path
	char *path;                 // path of the compiled bytecode file relative to interp->basedir
	struct ScopeObject *scope;  // a subscope of the built-in scope
	struct Code code;           // loaded from the path

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
