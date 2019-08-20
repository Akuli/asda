#include "import.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bcreader.h"
#include "code.h"
#include "interp.h"
#include "module.h"
#include "path.h"
#include "runner.h"
#include "type.h"
#include "objects/err.h"

static void destroy_types(struct Type **types)
{
	for (size_t i = 0; types[i]; i++)
		type_destroy(types[i]);
	free(types);
}

static bool read_bytecode_file(Interp *interp, const char *bcpath, char **srcpath, struct Code *code, struct Type ***types)
{
	assert(bcpath[0]);

	char *fullbcpath = path_concat(interp->basedir, bcpath);
	if (!fullbcpath) {
		errobj_set_oserr(interp, "getting the full path to '%s' failed", bcpath);
		return false;
	}

	size_t i = path_findlastslash(bcpath);
	char *dir = malloc(i+1);
	if (!dir) {
		free(fullbcpath);
		errobj_set_nomem(interp);
		return false;
	}
	memcpy(dir, bcpath, i);
	dir[i] = 0;

	FILE *f = fopen(fullbcpath, "rb");
	if (!f) {
		errobj_set_oserr(interp, "cannot open '%s'", fullbcpath);
		free(dir);
		free(fullbcpath);
		return false;
	}
	free(fullbcpath);

	struct BcReader bcr = bcreader_new(interp, f, dir);
	*srcpath = NULL;

	if (!bcreader_readasdabytes(&bcr))
		goto error;
	if (!( *srcpath = bcreader_readsourcepath(&bcr) ))
		goto error;
	if (!bcreader_readimports(&bcr))
		goto error;

	// TODO: handle import cycles
	for (size_t i = 0; bcr.imports[i]; i++)
		if (!module_get(interp, bcr.imports[i]) && !import(interp, bcr.imports[i]))
			goto error;

	if (!( *types = bcreader_readtypelist(&bcr) ))
		goto error;

	if (!bcreader_readcodepart(&bcr, code)) {
		destroy_types(*types);
		goto error;
	}

	// srcpath not freed here, the code needs it
	bcreader_destroy(&bcr);
	free(dir);
	fclose(f);
	return true;

error:
	bcreader_destroy(&bcr);
	free(*srcpath);
	free(dir);
	fclose(f);
	return false;
}

static bool run(Interp *interp, const struct Code *code)
{
	struct Runner rnr;
	if (!runner_init(&rnr, interp, code))
		return false;
	enum RunnerResult res = runner_run(&rnr);
	runner_free(&rnr);

	assert(res == RUNNER_ERROR || res == RUNNER_DIDNTRETURN);  // asda compiler shouldn't allow others
	return (res != RUNNER_ERROR);
}

bool import(Interp *interp, const char *path)
{
	struct Module *mod = malloc(sizeof(*mod));
	if (!mod)
		return false;

	mod->bcpath = malloc(strlen(path) + 1);
	if (!mod->bcpath) {
		free(mod);
		return false;
	}
	strcpy(mod->bcpath, path);

	if (!read_bytecode_file(interp, path, &mod->srcpath, &mod->code, &mod->types)) {
		free(mod->bcpath);
		free(mod);
		return false;
	}

	mod->runok = run(interp, &mod->code);
	module_add(interp, mod);
	return mod->runok;
}
