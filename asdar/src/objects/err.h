#ifndef OBJECTS_ERR_H
#define OBJECTS_ERR_H

#include "../interp.h"
#include "../object.h"
#include "../type.h"
#include "string.h"

extern const struct Type
	errobj_type_error,   // base class for other errors
	errobj_type_nomem,
	errobj_type_variable,
	errobj_type_value,
	errobj_type_os;

typedef struct ErrObject {
	OBJECT_HEAD
	StringObject *msgstr;
	// TODO: chained errors
	//       but maybe not as linked list?
	//       if linked list then how about multiple NoMemErrors chaining? avoid chaining onto itself

	/*
	when an error is thrown, the stack points to interp->stack and ownstack is false
	setting this up does not require a memory allocation, which is important (think no memory error)

	if the error is caught, interp->stack has to change, so the stack is copied here and ownstack is set to true
	this can fail with no memory error, but that's fine because error handlers can fail with no memory error anyway
	*/
	struct InterpStackItem *stack;
	size_t stacklen;
	bool ownstack;
} ErrObject;

// use this if you don't want to create a new error object
void errobj_set_obj(Interp *interp, ErrObject *err);


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

// sets ownstack to true and does all the other stuff commented near definition of ownstack
void errobj_beginhandling(Interp *interp, ErrObject *err);

// dump error message to stderr
void errobj_printstack(Interp *interp, ErrObject *err);


#endif   // OBJECTS_ERR_H
