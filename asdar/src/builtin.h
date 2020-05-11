#ifndef BUILTINS_H
#define BUILTINS_H

#include <stddef.h>
#include <stdbool.h>
#include "interp.h"
#include "object.h"


struct BuiltinFunc {
	bool ret;
	union {
		// return true for success, false for fail. No need to free or decref args.
		bool (*noret)(Interp *interp, Object *const *args);

		// return the return value of the asda function (as a new reference), or NULL for error
		Object* (*ret)(Interp *interp, Object *const *args);
	} func;
	size_t nargs;
};

extern const struct BuiltinFunc builtin_funcs[];
extern const size_t builtin_nfuncs;


#endif   // BUILTINS_H
