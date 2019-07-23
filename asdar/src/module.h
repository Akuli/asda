#ifndef MODULE_H
#define MODULE_H

#include "code.h"
#include "interp.h"
#include "objects/scope.h"

struct Module {
	// see interp->basedir comments for more details about the path
	// srcpath and compath are relative to interp->basedir
	char *srcpath;       // path of source file
	char *bcpath;        // path of compiled bytecode file
	ScopeObject *scope;  // a subscope of the built-in scope
	struct Code code;    // loaded from bcpath
	struct Type **types; // type_destroy()ed when the module is destroyed, NULL terminated

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
//   - mod->srcpath will be freed
//   - mod->bcpath will be freed
//   - each type of mod->types will be type_destroy()ed
//   - mod->types will be freed
//   - mod will be freed
void module_add(Interp *interp, struct Module *mod);

// called on interpreter exit
void module_destroyall(Interp *interp);

#endif  // MODULE_H
