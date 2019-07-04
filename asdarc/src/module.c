#include "module.h"
#include <assert.h>
#include <stdlib.h>
#include <string.h>
#include "code.h"
#include "interp.h"

const struct Module *module_get(Interp *interp, const char *path)
{
	struct Module *mod = interp->firstmod;
	while(mod) {
		int c = strcmp(path, mod->path);
		if (c < 0)
			mod = mod->left;
		else if (c > 0)
			mod = mod->right;
		else
			return mod;
	}
	return NULL;
}

void module_add(Interp *interp, struct Module *mod)
{
	struct Module **dest = &interp->firstmod;
	while (*dest) {
		int c = strcmp(mod->path, (*dest)->path);
		if (c < 0)
			dest = &( (*dest)->left );
		else if (c > 0)
			dest = &( (*dest)->right );
		else
			assert(0);
	}

	mod->left = NULL;
	mod->right = NULL;
	*dest = mod;
}


// feel free to do this differently if this recurses too bad
static void destroy_a_module(struct Module *mod)
{
	free(mod->path);
	OBJECT_DECREF(mod->scope);
	code_destroy(&mod->code);
	if (mod->left)
		destroy_a_module(mod->left);
	if (mod->right)
		destroy_a_module(mod->right);
	free(mod);
}

void module_destroyall(Interp *interp)
{
	destroy_a_module(interp->firstmod);
	interp->firstmod = NULL;
}
