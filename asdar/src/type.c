#include "type.h"
#include <stdlib.h>
#include "interp.h"
#include "object.h"
#include "objects/err.h"
#include "objects/func.h"

struct TypeFunc *type_func_new(Interp *interp, const struct Type **argtypes, size_t nargtypes, const struct Type *rettype)
{
	struct TypeFunc *res = malloc(sizeof(*res));
	if (!res) {
		free(argtypes);
		errobj_set_nomem(interp);
		return NULL;
	}

	res->kind = TYPE_FUNC;
	res->methods = NULL;
	res->nmethods = 0;
	res->argtypes = argtypes;
	res->nargtypes = nargtypes;
	res->rettype = rettype;
	return res;
}

void type_destroy(struct Type *t)
{
	switch(t->kind) {
	case TYPE_BASIC:
		break;
	case TYPE_FUNC:
		free( ((struct TypeFunc *)t)->argtypes );
		break;
	}

	for (size_t i = 0; i < t->nmethods; i++)
		OBJECT_DECREF(t->methods[i]);
	free(t->methods);
	free(t);
}
