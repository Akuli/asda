#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "import.h"
#include "interp.h"
#include "module.h"
#include "objtyp.h"
#include "path.h"
#include "objects/int.h"


int main(int argc, char **argv)
{
	char *basedir = NULL;

	if (argc != 2) {
		fprintf(stderr, "Usage: %s bytecodefile\n", argv[0]);
		return 2;
	}

	Interp interp;
	if (!interp_init(&interp, argv[0]))   // sets interp.errstr on error
		goto error_dont_destroy_interp;

	if (!( basedir = path_toabsolute(argv[1]) )) {
		interp_errstr_printf_errno(&interp,
			"finding absolute path of \"%s\" failed", argv[1]);
		goto error;
	}

	size_t i = path_findlastslash(basedir);
	basedir[i] = 0;
	interp.basedir = basedir;
	const char *relative = basedir + (i+1);

	if (!import(&interp, relative))
		goto error;

	free(basedir);
	module_destroyall(&interp);
	interp_destroy(&interp);

	return 0;

error:
	module_destroyall(&interp);
	interp_destroy(&interp);     // leaves errstr untouched
	// "fall through"

error_dont_destroy_interp:
	fprintf(stderr, "%s: error: %s\n", argv[0], interp.errstr);
	free(basedir);
	return 1;
}
