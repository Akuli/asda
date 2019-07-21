#ifndef TYPE_H
#define TYPE_H

#include "interp.h"
#include <stddef.h>

enum TypeKind {
	TYPE_BASIC,
	TYPE_FUNC,
};

// also include objects/func.h if you want to do something with the methods
struct FuncObject;

#define HEAD \
	enum TypeKind kind; \
	struct FuncObject **methods; \
	size_t nmethods;

struct Type {
	HEAD
};

// types of functions are TypeFunc structs
// 'struct TypeFunc *' can be casted to 'struct Type *'
// look up "common initial members" if you are not familiar with this technique
struct TypeFunc {
	HEAD
	const struct Type **argtypes;
	size_t nargtypes;
	const struct Type *rettype;   // NULL for void functions
};

#undef HEAD

// never runs for compile-time created types
void type_destroy(struct Type *t);

#define TYPE_BASIC_COMPILETIMECREATE(METHODS, NMETHODS) { \
	.kind = TYPE_BASIC, \
	.methods = (METHODS), \
	.nmethods = (NMETHODS), \
}

#define TYPE_FUNC_COMPILETIMECREATE(ARGT, NARGT, RETT) { \
	.kind = TYPE_FUNC, \
	.methods = NULL, \
	.nmethods = 0, \
	.argtypes = (ARGT), \
	.nargtypes = (NARGT), \
	.rettype = (RETT), \
}

// does NOT destroy each argtype, but will free argtypes eventually (immediately on error, later on success)
struct TypeFunc *type_func_new(Interp *interp, const struct Type **argtypes, size_t nargtypes, const struct Type *rettype);

#endif    // TYPE_H
