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
	if (argc != 2) {
		fprintf(stderr, "Usage: %s bytecodefile\n", argv[0]);
		return 2;
	}

	Interp interp;
	interp_init(&interp, argv[0]);

	char *basedir = NULL, *relative = NULL;
	if (!path_split(argv[1], &interp.basedir, &relative)) {
		errobj_set_oserr(&interp, "finding or splitting absolute path of '%s' failed", argv[1]);
		goto error;
	}

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
