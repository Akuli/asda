#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "code.h"
#include "import.h"
#include "interp.h"
#include "path.h"
#include "objects/err.h"
#include "stacktrace.h"


int main(int argc, char **argv)
{
	char *basedir = NULL;

	if (argc != 2) {
		fprintf(stderr, "Usage: %s bytecodefile\n", argv[0]);
		return 2;
	}

	Interp interp;
	interp_init(&interp, argv[0]);

	if (!( basedir = path_toabsolute(argv[1]) )) {
		errobj_set_oserr(&interp, "finding absolute path of '%s' failed", argv[1]);
		goto error;
	}

	size_t fullen = strlen(basedir);
	size_t i = path_findlastslash(basedir);
	basedir[i] = 0;
	interp.basedir = basedir;

	char *relative = malloc(fullen - i);
	if (!relative) {
		errobj_set_nomem(&interp);
		goto error;
	}
	strcpy(relative, basedir + (i+1));

	if (!import(&interp, relative))
		goto error;

	free(basedir);
	interp_destroy(&interp);

	return 0;

error:
	// if a stack trace was printed already, then interp.err is NULL
	if (interp.err) {
		stacktrace_print_raw(interp.err);
		OBJECT_DECREF(interp.err);
		interp.err = NULL;
	}

	free(basedir);
	interp_destroy(&interp);
	return 1;
}
