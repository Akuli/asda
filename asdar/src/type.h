#ifndef TYPE_H
#define TYPE_H

#include <stdbool.h>
#include <stddef.h>
#include "interp.h"

// forward declaring because these are defined in files that include this file
// also include other files if you want to do something with these
struct Object;
struct AsdaInstObject;
struct FuncObject;


enum TypeAttrKind {
	TYPE_ATTR_METHOD,
	TYPE_ATTR_ASDA,
};

struct TypeAttr {
	enum TypeAttrKind kind;

	/*
	this is not used for TYPE_ATTR_ASDA

	this can be NULL in methods of asda classes
	that's needed because types are read from the bytecode before running the code (creates the func objects)

	if this isn't NULL, it takes 'this' as first argument
	*/
	struct FuncObject *method;
};


// no idea why this is needed, iwyu appears to be dumb
// IWYU pragma: no_forward_declare Type

enum TypeKind {
	TYPE_BASIC,
	TYPE_FUNC,
	TYPE_ASDACLASS,
};

#define HEAD \
	enum TypeKind kind; \
	const struct Type *base;    /* Object has no base class, so this is NULL for it */ \
	struct Object* (*constructor)(Interp *, const struct Type *, struct Object *const *args, size_t nargs); \
	struct TypeAttr *attrs; \
	size_t nattrs;

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

/*
asda attrs are first in ->attrs, methods are after them

	             ------------------------
	attrs =      | asda attrs | methods |
	             ------------------------

	nattrs =     <---------------------->
	nasdaattrs = <------------>

the value of the ith asda attr is instance->attrvals[i], where instance is an AsdaInstObject
*/
struct TypeAsdaClass {
	HEAD
	size_t nasdaattrs;
};

#undef HEAD


// if you change this, note that there is a thing in type.c that fills in the fields without this
#define TYPE_BASIC_COMPILETIMECREATE(BASE, CONSTRUCTOR, ATTRS, NATTRS) { \
	.kind = TYPE_BASIC, \
	.base = (BASE) ? (BASE) : &type_object, \
	.constructor = (CONSTRUCTOR), \
	.attrs = (ATTRS), \
	.nattrs = (NATTRS), \
}

// the "..." is argument types, in braces
#define TYPE_FUNC_COMPILETIMECREATE(VARNAME, RETTYPE, ...) \
	static const struct Type *VARNAME##_argtypes[] = __VA_ARGS__; \
	static const struct TypeFunc VARNAME = { \
		.kind = TYPE_FUNC, \
		.base = &type_object, \
		.constructor = NULL, \
		.attrs = NULL, \
		.nattrs = 0, \
		.argtypes = VARNAME##_argtypes, \
		.nargtypes = sizeof(VARNAME##_argtypes)/sizeof(VARNAME##_argtypes[0]), \
		.rettype = (RETTYPE), \
	}


// the Object base-class-of-everything type
extern const struct Type type_object;

// never runs for compile-time created types
void type_destroy(struct Type *t);

// will free(argtypes) eventually (immediately on error, later on success)
struct TypeFunc *type_func_new(Interp *interp, const struct Type **argtypes, size_t nargtypes, const struct Type *rettype);

// sets the FuncObject of each method to NULL
struct TypeAsdaClass *type_asdaclass_new(Interp *interp, size_t nasdaattrs, size_t nmethods);

// type A is compatible with type B, if A is subclass of B or the types are the same
bool type_compatiblewith(const struct Type *sub, const struct Type *par);

#endif    // TYPE_H
