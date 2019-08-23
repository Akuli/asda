#include "module.h"
#include <assert.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "code.h"
#include "interp.h"
#include "type.h"

const struct Module *module_get(Interp *interp, const char *path)
{
	struct Module *mod = interp->firstmod;
	while(mod) {
		int c = strcmp(path, mod->bcpath);
		if (c < 0)
			mod = mod->left;
		else if (c > 0)
			mod = mod->right;
		else {
			assert(mod->runok);
			return mod;
		}
	}
	return NULL;
}

void module_add(Interp *interp, struct Module *mod)
{
	struct Module **dest = &interp->firstmod;
	while (*dest) {
		int c = strcmp(mod->bcpath, (*dest)->bcpath);
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


static void destroy_paths_and_code(const struct Module *mod)
{
	if (!mod)
		return;

	free(mod->srcpath);
	free(mod->bcpath);
	code_destroy(&mod->code);
	destroy_paths_and_code(mod->left);
	destroy_paths_and_code(mod->right);
}

// feels good to destroy types last because other stuff may depend on them
static void destroy_types_and_free(struct Module *mod)
{
	if (!mod)
		return;

	for (size_t i = 0; mod->types[i]; i++)
		type_destroy(mod->types[i]);
	free(mod->types);
	destroy_types_and_free(mod->left);
	destroy_types_and_free(mod->right);
	free(mod);
}

void module_destroyall(Interp *interp)
{
	// this does nothing if interp->firstmod is NULL
	destroy_paths_and_code(interp->firstmod);
	destroy_types_and_free(interp->firstmod);
	interp->firstmod = NULL;
}
