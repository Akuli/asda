// asda functions written in c

#ifndef CFUNC_H
#define CFUNC_H

#include <stddef.h>
#include <stdbool.h>
#include "interp.h"
#include "object.h"

struct CFunc {
	const char *name;
	size_t nargs;
	bool ret;
	union {
		// return true for success, false for fail. No need to free or decref args.
		bool (*noret)(Interp *interp, Object *const *args);

		// return the return value of the asda function (as a new reference), or NULL for error
		struct Object* (*ret)(Interp *interp, Object *const *args);
	} func;
};

// cfuncs should be an array of cfuncs, ending to cfunc whose name is NULL
// using this function doesn't magically make the asda compiler aware of cfuncs
bool cfunc_addmany(Interp *interp, const struct CFunc *cfuncs);

// bcreader uses this, returns NULL for not found, never fails otherwise
const struct CFunc *cfunc_get(Interp *interp, const char *name);


#endif   // CFUNC_H
