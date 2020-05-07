// bytecode reader

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
	char *srcpath;   // FIXME: when to free this?
	const char *indirname;   // relative to interp->basedir, must NOT free() until bc reader no longer needed
	uint32_t lineno;
	char **imports;          // NULL terminated
};

// never fails
struct BcReader bcreader_new(Interp *interp, FILE *in, const char *indirname);

// does not do anything to things passed as arguments to bcreader_new
void bcreader_destroy(const struct BcReader *bcr);

bool bcreader_readasdabytes(struct BcReader *bcr);

// sets bcr->module->srcpath, it must be free()d unless bcreader_readcodepart() succeeds
bool bcreader_readsourcepath(struct BcReader *bcr);

// returns nonnegative number to indicate location of main function to run, or -1 on error
long bcreader_readcodepart(struct BcReader *bcr);


#endif   // BCREADER_H
