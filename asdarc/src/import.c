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
#include "objtyp.h"
#include "path.h"
#include "runner.h"
#include "objects/scope.h"

static bool read_bytecode_file(Interp *interp, const char *path, struct Code *code)
{
	assert(path[0]);

	char *fullpath = path_concat(interp->basedir, path);
	if (!fullpath) {
		interp_errstr_printf_errno(interp, "getting the full path to '%s' failed", path);
		return false;
	}

	size_t i = path_findlastslash(path);
	char *dir = malloc(i+1);
	if (!dir) {
		free(fullpath);
		interp_errstr_nomem(interp);
		return false;
	}
	memcpy(dir, path, i);
	dir[i] = 0;

	FILE *f = fopen(fullpath, "rb");
	free(fullpath);
	if (!f) {
		interp_errstr_printf_errno(interp, "cannot open '%s'", fullpath);
		return false;
	}

	struct BcReader bcr = bcreader_new(interp, f, dir);
	if (!bcreader_readasdabytes(&bcr))
		goto error;
	if (!bcreader_readimports(&bcr))
		goto error;

	// TODO: handle import cycles
	for (size_t i = 0; i < bcr.nimports; i++)
		if (!module_get(interp, path) && !import(interp, bcr.imports[i]))
			goto error;

	if (!bcreader_readcodepart(&bcr, code))
		goto error;

	bcreader_destroy(&bcr);
	free(dir);
	fclose(f);
	return true;

error:
	bcreader_destroy(&bcr);
	free(dir);
	fclose(f);
	return false;
}

static bool run(Interp *interp, Object *scope, struct Code code)
{
	struct Runner rnr;
	runner_init(&rnr, interp, scope, code);
	enum RunnerResult res = runner_run(&rnr);
	runner_free(&rnr);

	switch(res) {
	case RUNNER_DIDNTRETURN:
		return true;
	case RUNNER_ERROR:
		return false;
	default:
		assert(0);  // asda compiler shouldn't allow doing anything else
	}
}

bool import(Interp *interp, const char *path)
{
	struct Module *mod = malloc(sizeof(*mod));
	if (!mod)
		return false;

	mod->path = malloc(strlen(path) + 1);
	if (!mod->path) {
		free(mod);
		return false;
	}
	strcpy(mod->path, path);

	if (!read_bytecode_file(interp, path, &mod->code)) {
		free(mod->path);
		free(mod);
		return false;
	}

	if (!( mod->scope = scopeobj_newsub(interp, interp->builtinscope, mod->code.nlocalvars) )) {
		code_destroy(&mod->code);
		free(mod->path);
		free(mod);
		return false;
	}

	if (!run(interp, mod->scope, mod->code)) {
		OBJECT_DECREF(mod->scope);
		code_destroy(&mod->code);
		free(mod->path);
		free(mod);
		return false;
	}

	module_add(interp, mod);
	return true;
}
