#ifndef TYPE_H
#define TYPE_H

#include <stddef.h>
#include "interp.h"

// no idea why this is needed, iwyu appears to be dumb
// IWYU pragma: no_forward_declare Type

enum TypeKind {
	TYPE_BASIC,
	TYPE_FUNC,
};

// also include object.h and objects/func.h if you want to do something with these
struct Object;
struct FuncObject;

#define HEAD \
	enum TypeKind kind; \
	struct Object* (*constructor)(Interp *, const struct Type *, struct Object *const *args, size_t nargs); \
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

#define TYPE_BASIC_COMPILETIMECREATE(METHODS, NMETHODS, CONSTRUCTOR) { \
	.kind = TYPE_BASIC, \
	.constructor = (CONSTRUCTOR), \
	.methods = (METHODS), \
	.nmethods = (NMETHODS), \
}

// the "..." is argument types, in braces
#define TYPE_FUNC_COMPILETIMECREATE(VARNAME, RETTYPE, ...) \
	static const struct Type *VARNAME##_argtypes[] = __VA_ARGS__; \
	static const struct TypeFunc VARNAME = { \
		.kind = TYPE_FUNC, \
		.constructor = NULL, \
		.methods = NULL, \
		.nmethods = 0, \
		.argtypes = VARNAME##_argtypes, \
		.nargtypes = sizeof(VARNAME##_argtypes)/sizeof(VARNAME##_argtypes[0]), \
		.rettype = (RETTYPE), \
	}

// does NOT destroy each argtype, but will free argtypes eventually (immediately on error, later on success)
struct TypeFunc *type_func_new(Interp *interp, const struct Type **argtypes, size_t nargtypes, const struct Type *rettype);

#endif    // TYPE_H
