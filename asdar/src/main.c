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
#include "objects/err.h"
#include "objects/int.h"
#include "objects/string.h"


static void print_error(Interp *interp)
{
	struct StringObject *strobj = errobj_getstring(interp->err);
	assert(strobj);   // that cannot fail
	OBJECT_DECREF(interp->err);
	interp->err = NULL;

	const char *str;
	size_t len;
	if (stringobj_toutf8(strobj, &str, &len)) {
		fprintf(stderr, "%s: error: %s\n", interp->argv0, str);
		OBJECT_DECREF(strobj);
		return;
	}

	OBJECT_DECREF(strobj);
	OBJECT_DECREF(interp->err);
	interp->err = NULL;
	fprintf(stderr, "%s: an error occurred, and another error occurred while printing the error. Sorry. :(\n", interp->argv0);
}


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
	print_error(&interp);
	module_destroyall(&interp);
	interp_destroy(&interp);
	free(basedir);
	return 1;
}
