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

bool import(Interp *interp, char *bcpath)
{
	assert(bcpath[0]);
	bool ok = bcreader_read(interp, bcpath);
	if (!ok)
		return false;

	// TODO: handle import cycles

	return run_module(interp, &interp->mods.ptr[interp->mods.len - 1]);
}
