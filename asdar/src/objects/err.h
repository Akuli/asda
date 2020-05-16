#ifndef OBJECTS_ERR_H
#define OBJECTS_ERR_H

#include <stdbool.h>
#include <stddef.h>
#include "../interp.h"
#include "../object.h"
#include "string.h"

/*
the interpreter generally doesn't know much about types. However, it must know the
types of error objects to figure out whether an error should be caught or not.
*/
struct ErrType {
	const char *name;
};

extern const struct ErrType
	errtype_nomem,
	errtype_variable,
	errtype_value,
	errtype_os;

typedef struct ErrObject {
	struct ObjectHead head;
	const struct ErrType *type;
	StringObject *msgstr;
} ErrObject;

// use this if you don't want to create a new error object
void errobj_set_obj(Interp *interp, ErrObject *err);


// see string.h for info about the format strings

// use this when other error setting functions aren't suitable
void errobj_set(Interp *interp, const struct ErrType *errtype, const char *fmt, ...);

// use this when malloc or one of its friends returns NULL
void errobj_set_nomem(Interp *interp);

/*
if errno is nonzero, adds errno and a human-friendly errno description to the message

example:

	FILE *f = fopen(path, "r");
	if (!f) {
		errobj_set_oserr(interp, "cannot open '%s'", path);
		return NULL;
	}
*/
void errobj_set_oserr(Interp *interp, const char *fmt, ...);

// for cfunc_addmany
extern const struct CFunc errobj_cfuncs[];

#endif   // OBJECTS_ERR_H
