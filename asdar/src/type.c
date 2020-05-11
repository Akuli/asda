#include "type.h"
#include <stdbool.h>
#include <stdlib.h>
#include "interp.h"
#include "objects/asdainst.h"
#include "objects/err.h"

// can't use TYPE_BASIC_COMPILETIMECREATE because it disallows making the base NULL
const struct Type type_object = {
	.kind = TYPE_BASIC,
	.base = NULL,
	.constructor = NULL,
	.attrs = NULL,
	.nattrs = 0,
};


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


void type_destroy(struct Type *t)
{
	free(t->attrs);
	free(t);
}


// TODO: handle function types
bool type_compatiblewith(const struct Type *sub, const struct Type *par)
{
	for (const struct Type *t = sub; t; t = t->base)
		if (t == par)
			return true;
	return false;
}
