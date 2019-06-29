#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "bcreader.h"
#include "code.h"
#include "interp.h"
#include "objtyp.h"
#include "path.h"
#include "runner.h"
#include "objects/int.h"
#include "objects/scope.h"

static bool run(struct Interp *interp, struct Code code)
{
	struct Object *scope = scopeobj_newsub(interp, interp->builtinscope, code.nlocalvars);
	if(!scope)
		return false;

	struct Runner rnr;
	runner_init(&rnr, interp, scope, code);  // increfs scope as needed
	OBJECT_DECREF(scope);

	enum RunnerResult res = runner_run(&rnr);
	runner_free(&rnr);

	switch(res) {
	case RUNNER_DIDNTRETURN:
		return true;
	case RUNNER_ERROR:
		return false;
	default:
		assert(0);  // compiler shouldn't allow anything else
	}
}


int main(int argc, char **argv)
{
	char **imports = NULL;
	uint16_t nimports = 0;
	char *dir = NULL;
	FILE *f = NULL;

	if (argc != 2) {
		fprintf(stderr, "Usage: %s bytecodefile\n", argv[0]);
		return 2;
	}

	struct Interp interp;
	if (!interp_init(&interp, argv[0]))   // sets interp.errstr on error
		goto error_dont_destroy_interp;

	if (!( dir = path_toabsolute(argv[1]) )) {
		interp_errstr_printf_errno(&interp,
			"finding absolute path of \"%s\" failed", argv[1]);
		goto error;
	}
	dir[path_findlastslash(dir)] = 0;

	if (!( f = fopen(argv[1], "rb") )) {
		interp_errstr_printf_errno(&interp, "cannot open %s", argv[1]);
		goto error;
	}

	struct BcReader bcr = bcreader_new(&interp, f, dir);
	struct Code code;

	if (!bcreader_readasdabytes(&bcr))
		goto error;
	if (!bcreader_readimports(&bcr, &imports, &nimports))
		goto error;
	if (!bcreader_readcodepart(&bcr, &code))
		goto error;
	fclose(f);
	f = NULL;

	bool ok = run(&interp, code);
	code_destroy(&code);
	if (!ok)
		goto error;

	free(dir);
	bcreader_freeimports(imports, nimports);
	interp_destroy(&interp);

	return 0;

error:
	if (imports)
		bcreader_freeimports(imports, nimports);
	if(f)
		fclose(f);
	interp_destroy(&interp);     // leaves errstr untouched
	// "fall through"

error_dont_destroy_interp:
	fprintf(stderr, "%s: error: %s\n", argv[0], interp.errstr);
	free(dir);
	return 1;
}
