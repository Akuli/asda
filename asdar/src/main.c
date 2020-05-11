#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "import.h"
#include "interp.h"
#include "path.h"
#include "objects/err.h"


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

	size_t i = path_findlastslash(basedir);
	basedir[i] = 0;
	interp.basedir = basedir;
	const char *relative = basedir + (i+1);

	if (!import(&interp, relative))
		goto error;

	free(basedir);
	interp_destroy(&interp);

	return 0;

error:
	assert(0 );    // TODO
}
