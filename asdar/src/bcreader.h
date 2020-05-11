// bytecode reader

#ifndef BCREADER_H
#define BCREADER_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "interp.h"


struct BcReader {
	Interp *interp;
	FILE *in;
	char *srcpath;   // FIXME: when to free this?
	const char *indirname;   // relative to interp->basedir, must NOT free() until bc reader no longer needed
	uint32_t lineno;
};

// never fails
struct BcReader bcreader_new(Interp *interp, FILE *in, const char *indirname);

bool bcreader_readasdabytes(struct BcReader *bcr);

// sets bcr->module->srcpath, it must be free()d unless bcreader_readcodepart() succeeds
bool bcreader_readsourcepath(struct BcReader *bcr);

// returns nonnegative number to indicate location of main function to run, or -1 on error
long bcreader_readcodepart(struct BcReader *bcr);


#endif   // BCREADER_H
