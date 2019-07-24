#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include "import.h"
#include "interp.h"
#include "module.h"
#include "object.h"
#include "path.h"
#include "type.h"
#include "objects/err.h"
#include "objects/int.h"
#include "objects/string.h"


int main(int argc, char **argv)
{
	char *basedir = NULL;

	if (argc != 2) {
		fprintf(stderr, "Usage: %s bytecodefile\n", argv[0]);
		return 2;
	}

	Interp interp;
	if (!interp_init(&interp, argv[0]))
		goto error;

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
	module_destroyall(&interp);
	interp_destroy(&interp);

	return 0;

error:
	assert(1);   // because c syntax
	ErrObject *e = interp.err;
	interp.err = NULL;
	errobj_printstack(&interp, e);
	OBJECT_DECREF(e);

	module_destroyall(&interp);
	interp_destroy(&interp);
	free(basedir);
	return 1;
}
