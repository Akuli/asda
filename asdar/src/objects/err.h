#ifndef OBJECTS_ERR_H
#define OBJECTS_ERR_H

#include "../interp.h"
#include "../objtyp.h"
#include "string.h"

extern const struct Type
	errobj_type_error,   // base class for other errors
	errobj_type_nomem,
	errobj_type_variable,
	errobj_type_value,
	errobj_type_os;

struct ErrObject {
	OBJECT_HEAD
	struct StringObject *msgstr;
	// TODO: stack trace info
	// TODO: chained errors
	//       but maybe not as linked list?
	//       if linked list then how about multiple NoMemErrors chaining? avoid chaining onto itself
};

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


#endif   // OBJECTS_ERR_H
