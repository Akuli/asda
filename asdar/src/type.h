#ifndef TYPE_H
#define TYPE_H

#include <stdbool.h>
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

// the Object base-class-of-everything type
extern const struct Type type_object;

#define HEAD \
	enum TypeKind kind; \
	const struct Type *base;    /* Object has no base class, so this is NULL for it */ \
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

// if you change this, note that there is a thing in type.c that fills in the fields without this
#define TYPE_BASIC_COMPILETIMECREATE(BASE, CONSTRUCTOR, METHODS, NMETHODS) { \
	.kind = TYPE_BASIC, \
	.base = (BASE) ? (BASE) : &type_object, \
	.constructor = (CONSTRUCTOR), \
	.methods = (METHODS), \
	.nmethods = (NMETHODS), \
}

// the "..." is argument types, in braces
#define TYPE_FUNC_COMPILETIMECREATE(VARNAME, RETTYPE, ...) \
	static const struct Type *VARNAME##_argtypes[] = __VA_ARGS__; \
	static const struct TypeFunc VARNAME = { \
		.kind = TYPE_FUNC, \
		.base = &type_object, \
		.constructor = NULL, \
		.methods = NULL, \
		.nmethods = 0, \
		.argtypes = VARNAME##_argtypes, \
		.nargtypes = sizeof(VARNAME##_argtypes)/sizeof(VARNAME##_argtypes[0]), \
		.rettype = (RETTYPE), \
	}

// does NOT destroy each argtype, but will free argtypes eventually (immediately on error, later on success)
struct TypeFunc *type_func_new(Interp *interp, const struct Type **argtypes, size_t nargtypes, const struct Type *rettype);

// type A is compatible with type B, if A is subclass of B or the types are the same
bool type_compatiblewith(const struct Type *sub, const struct Type *par);

#endif    // TYPE_H
