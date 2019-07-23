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
	const char *indirname;   // relative to interp->basedir, must NOT free() until bc reader no longer needed
	uint32_t lineno;
	char *srcpath;
	char **imports;          // NULL terminated
	struct Type **typelist;  // the return value of bcreader_readtypelist
};

// never fails
struct BcReader bcreader_new(Interp *interp, FILE *in, const char *indirname);

// does not do anything to things passed as arguments to bcreader_new
void bcreader_destroy(const struct BcReader *bcr);

bool bcreader_readasdabytes(struct BcReader *bcr);

// on error, returns NULL
// on success, return value must be free()d unless bcreader_readcodepart() succeeds too
char *bcreader_readsourcepath(struct BcReader *bcr);

// puts a mallocced array of mallocced strings to bcr->imports
bool bcreader_readimports(struct BcReader *bcr);

// if this returns non-NULL, the return value is a NULL-terminated array
// each item must be type_destroy()ed and the array must be free()d
struct Type **bcreader_readtypelist(struct BcReader *bcr);

// call bcreader_readtypelist and don't free the stuff it returns before calling this
// if this succeeds (returns true), the res should be bc_destroy()ed
// the resulting code uses the return value of bcreader_readsourcepath()
bool bcreader_readcodepart(struct BcReader *bcr, struct Code *res);


#endif   // BCREADER_H
