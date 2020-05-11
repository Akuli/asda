#include "import.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bcreader.h"
#include "interp.h"
#include "path.h"
#include "run.h"
#include "objects/err.h"

bool import(Interp *interp, const char *bcpath)
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

	long mainidx;
	if (!bcreader_readasdabytes(&bcr)
		|| !bcreader_readsourcepath(&bcr)
		|| (mainidx = bcreader_readcodepart(&bcr)) < 0
		)
	{
		goto error;
	}

	// TODO: handle import cycles

	run(interp, (size_t)mainidx);

	// srcpath not freed here, the code needs it
	free(dir);
	fclose(f);
	return true;

error:
	free(dir);
	fclose(f);
	return false;
}
