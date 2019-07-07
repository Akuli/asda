#ifndef OBJECTS_ERR_H
#define OBJECTS_ERR_H

#include "../interp.h"
#include "../objtyp.h"

extern const struct Type
	errobj_type_error,   // base class for other errors
	errobj_type_nomem,
	errobj_type_variable,
	errobj_type_value,
	errobj_type_os;

// see string.h for info about the format strings

// use this when other error setting functions aren't suitable
void errobj_set(Interp *interp, const struct Type *errtype, const char *fmt, ...);

// use this when {m,re,c}alloc returns NULL
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

// returns String object as a new reference, never fails
Object *errobj_getstring(Object *err);


#endif   // OBJECTS_ERR_H
