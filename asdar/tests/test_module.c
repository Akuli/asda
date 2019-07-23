#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <src/code.h>
#include <src/interp.h>
#include <src/module.h>
#include <src/type.h>
#include <src/objects/scope.h>
#include "util.h"

static struct Module *create_test_module(Interp *interp, const char *name)
{
	struct Module *mod = malloc(sizeof *mod);
	assert(mod);

	mod->srcpath = malloc(strlen(name) + 1);
	mod->bcpath = malloc(strlen(name) + 1);
	assert(mod->srcpath);
	assert(mod->bcpath);
	strcpy(mod->srcpath, name);
	strcpy(mod->bcpath, name);

	mod->scope = scopeobj_newsub(interp, interp->builtinscope, 24);
	assert(mod->scope);

	mod->code = (struct Code){
		.srcpath = mod->srcpath,
		.ops = NULL,
		.nops = 0,
		.nlocalvars = 24,
	};

	mod->types = malloc(1 * sizeof(mod->types[0]));
	assert(mod->types);
	mod->types[0] = NULL;

	return mod;
}

TEST(module_create_and_destroying_and_getting)
{
	struct Module *a = create_test_module(interp, "a");
	struct Module *b = create_test_module(interp, "b");
	struct Module *c = create_test_module(interp, "c");
	struct Module *d = create_test_module(interp, "d");
	struct Module *e = create_test_module(interp, "e");

	/*
	     b
	    / \
	   a   c
	        \
	         e
	        /
	       d
	*/

	module_add(interp, b);
	module_add(interp, a);
	module_add(interp, c);
	module_add(interp, e);
	module_add(interp, d);

	assert(interp->firstmod == b);

	assert(a->left == NULL);
	assert(a->right == NULL);
	assert(b->left == a);
	assert(b->right == c);
	assert(c->left == NULL);
	assert(c->right == e);
	assert(d->left == NULL);
	assert(d->right == NULL);
	assert(e->left == d);
	assert(e->right == NULL);

	assert(module_get(interp, "a") == a);
	assert(module_get(interp, "b") == b);
	assert(module_get(interp, "c") == c);
	assert(module_get(interp, "d") == d);
	assert(module_get(interp, "e") == e);
	assert(module_get(interp, "f") == NULL);
	assert(module_get(interp, "") == NULL);
	assert(module_get(interp, "asd") == NULL);

	module_destroyall(interp);
	assert(!interp->firstmod);
}

TEST(module_destroyall_no_modules)
{
	assert(!interp->firstmod);
	module_destroyall(interp);
	assert(!interp->firstmod);
}
