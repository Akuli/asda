#include "module.h"
#include <assert.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "code.h"
#include "interp.h"
#include "type.h"
#include "object.h"

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


// asda classes may refer to objects that are instances of other asda classes
// in this way, an asda class may depend on another asda class, so that destroying order matters
// there's no good way to figure out what the correct destroying order should be
// the solution is to remove the dependency
static void set_methods_to_null(struct TypeAsdaClass *tac)
{
	for (size_t i = 0; i < tac->nattrs; i++) {
		if (tac->attrs[i].kind == TYPE_ATTR_METHOD && tac->attrs[i].method) {
			OBJECT_DECREF((Object *) tac->attrs[i].method);
			tac->attrs[i].method = NULL;
		}
	}
}

static void destroy_most_things(const struct Module *mod)
{
	if (!mod)
		return;

	free(mod->srcpath);
	free(mod->bcpath);
	code_destroy(mod->code);

	for (size_t i = 0; i < mod->nexports; i++)
		if (mod->exports[i])
			OBJECT_DECREF(mod->exports[i]);
	free(mod->exports);

	for (size_t i = 0; mod->types[i]; i++)
		if (mod->types[i]->kind == TYPE_ASDACLASS)
			set_methods_to_null((struct TypeAsdaClass *) mod->types[i]);

	destroy_most_things(mod->left);
	destroy_most_things(mod->right);
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
	destroy_most_things(interp->firstmod);
	destroy_types_and_free(interp->firstmod);
	interp->firstmod = NULL;
}
