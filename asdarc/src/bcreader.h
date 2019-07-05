// bc reader

#ifndef BCREADER_H
#define BCREADER_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "code.h"
#include "interp.h"


struct BcReader {
	Interp *interp;
	FILE *in;
	const char *indirname;   // relative to interp->basedir, must NOT free() until bc reader no longer needed
	uint32_t lineno;
	char **imports;
	size_t nimports;
};

// never fails
struct BcReader bcreader_new(Interp *interp, FILE *in, const char *indirname);

// does not do anything to things passed as arguments to bcreader_new
void bcreader_destroy(const struct BcReader *bcr);

bool bcreader_readasdabytes(struct BcReader *bcr);

// puts a mallocced array of mallocced strings to paths
// sets paths to NULL and npaths to 0 on error
bool bcreader_readimports(struct BcReader *bcr);

// if this succeeds (returns true), the res should be bc_destroy()ed
bool bcreader_readcodepart(struct BcReader *bcr, struct Code *res);


#endif   // BCREADER_H
