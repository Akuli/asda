// bytecode reader

#ifndef BCREADER_H
#define BCREADER_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "code.h"
#include "interp.h"
#include "module.h"


struct BcReader {
	Interp *interp;
	FILE *in;
	const char *indirname;   // relative to interp->basedir, must NOT free() until bc reader no longer needed
	struct Module *module;
	uint32_t lineno;
	char **imports;          // NULL terminated
};

// never fails
struct BcReader bcreader_new(Interp *interp, FILE *in, const char *indirname, struct Module *mod);

// does not do anything to things passed as arguments to bcreader_new
void bcreader_destroy(const struct BcReader *bcr);

bool bcreader_readasdabytes(struct BcReader *bcr);

// sets bcr->module->srcpath, it must be free()d unless bcreader_readcodepart() succeeds
bool bcreader_readsourcepath(struct BcReader *bcr);

// puts a mallocced array of mallocced strings to bcr->imports
bool bcreader_readimports(struct BcReader *bcr);

// sets bcr->module->nexports and allocates bcr->module->exports
bool bcreader_readexports(struct BcReader *bcr);

// sets bdr->module->types
bool bcreader_readtypelist(struct BcReader *bcr);

// call bcreader_readtypelist and don't free the stuff it returns before calling this
// if this succeeds (returns true), the res should be bc_destroy()ed
// the resulting code uses the return value of bcreader_readsourcepath()
bool bcreader_readcodepart(struct BcReader *bcr, struct Code *res);


#endif   // BCREADER_H
