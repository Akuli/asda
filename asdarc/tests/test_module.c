#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include <src/module.h>
#include <src/objects/scope.h>
#include "util.h"

static struct Module *create_test_module(Interp *interp, const char *name)
{
	struct Module *mod = malloc(sizeof *mod);
	assert(mod);

	mod->path = malloc(strlen(name) + 1);
	assert(mod->path);
	strcpy(mod->path, name);

	mod->scope = scopeobj_newsub(interp, interp->builtinscope, 24);
	assert(mod->scope);

	mod->code = (struct Code){
		.ops = NULL,
		.nops = 0,
		.nlocalvars = 24,
	};

	return mod;
}

TEST(module_creation_and_destroying)
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

	module_destroyall(interp);
	assert(!interp->firstmod);
}
