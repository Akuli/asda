#include "type.h"
#include <stdbool.h>
#include <stdlib.h>
#include "interp.h"
#include "object.h"
#include "objects/asdainst.h"
#include "objects/err.h"
#include "objects/func.h"   // IWYU pragma: keep

// can't use TYPE_BASIC_COMPILETIMECREATE because it disallows making the base NULL
const struct Type type_object = {
	.kind = TYPE_BASIC,
	.base = NULL,
	.constructor = NULL,
	.attrs = NULL,
	.nattrs = 0,
};


struct TypeFunc *type_func_new(Interp *interp, const struct Type **argtypes, size_t nargtypes, const struct Type *rettype)
{
	struct TypeFunc *res = malloc(sizeof(*res));
	if (!res) {
		free(argtypes);
		errobj_set_nomem(interp);
		return NULL;
	}

	res->kind = TYPE_FUNC;
	res->base = &type_object;
	res->constructor = NULL;
	res->attrs = NULL;
	res->nattrs = 0;
	res->argtypes = argtypes;
	res->nargtypes = nargtypes;
	res->rettype = rettype;
	return res;
}

struct TypeAsdaClass *type_asdaclass_new(Interp *interp, size_t nasdaattrs, size_t nmethods)
{
	struct TypeAsdaClass *res = malloc(sizeof(*res));
	if (!res){
		errobj_set_nomem(interp);
		return NULL;
	}

	if (nasdaattrs + nmethods == 0)
		res->attrs = NULL;
	else {
		res->attrs = malloc(sizeof(res->attrs[0]) * (nasdaattrs + nmethods));
		if (!res->attrs) {
			free(res);
			errobj_set_nomem(interp);
			return NULL;
		}
	}

	for (size_t i = 0; i < nasdaattrs; i++)
		res->attrs[i].kind = TYPE_ATTR_ASDA;
	for (size_t i = nasdaattrs; i < nasdaattrs + nmethods; i++) {
		res->attrs[i].kind = TYPE_ATTR_METHOD;
		res->attrs[i].method = NULL;
	}

	res->kind = TYPE_ASDACLASS;
	res->base = &type_object;
	res->constructor = asdainstobj_constructor;
	res->nattrs = nasdaattrs + nmethods;
	res->nasdaattrs = nasdaattrs;
	return res;
}

struct TypeGeneric *type_generic_new(Interp *interp, const struct Type *basetype, const struct Type **generics, size_t ngenerics)
{
	struct TypeGeneric *res = malloc(sizeof(*res));
	if (!res) {
		free(generics);
		errobj_set_nomem(interp);
		return NULL;
	}

	*(struct Type *)res = *basetype;
	res->kind = TYPE_GENERIC;
	res->generics = generics;
	res->ngenerics = ngenerics;
	return res;
}


void type_destroy(struct Type *t)
{
	switch(t->kind) {
	case TYPE_FUNC:
		free( ((struct TypeFunc *)t)->argtypes );
		// currently functions have no attributes
		// if this changes, all attrs will be compile-time created, and this will do the right thing anyway
		break;

	case TYPE_BASIC:
	case TYPE_ASDACLASS:
		for (size_t i = 0; i < t->nattrs; i++)
			if (t->attrs[i].kind == TYPE_ATTR_METHOD && t->attrs[i].method)
				OBJECT_DECREF(t->attrs[i].method);
		free(t->attrs);
		break;

	case TYPE_GENERIC:
		// see type_generic_new
		// everything except t->generics is copied from the base type with no increfs etc
		// because it is assumed that the base type is not destroyed before this type
		free( ((struct TypeGeneric *)t)->generics );
		break;
	}

	free(t);
}


// TODO: handle generics and function types
bool type_compatiblewith(const struct Type *sub, const struct Type *par)
{
	for (const struct Type *t = sub; t; t = t->base)
		if (t == par)
			return true;
	return false;
}
