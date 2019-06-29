// bc reader

#ifndef BCREADER_H
#define BCREADER_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "code.h"
#include "interp.h"


struct BcReader {
	struct Interp *interp;
	FILE *in;
	const char *indirname;
	uint32_t lineno;
};

// never fails
// TODO: decide when indirname can be freed and change all codes accordingly
struct BcReader bcreader_new(struct Interp *interp, FILE *in, const char *indirname);

bool bcreader_readasdabytes(struct BcReader *bcr);

// puts a mallocced array of mallocced strings to paths
// sets paths to NULL and npaths to 0 on error
bool bcreader_readimports(struct BcReader *bcr, char ***paths, uint16_t *npaths);
void bcreader_freeimports(char **paths, uint16_t npaths);

// if this succeeds (returns true), the res should be bc_destroy()ed
bool bcreader_readcodepart(struct BcReader *bcr, struct Code *res);


#endif   // BCREADER_H
