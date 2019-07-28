#include "asdainst.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "../interp.h"
#include "../object.h"
#include "../type.h"
#include "err.h"

static void destroy_asda_instance(Object *rawobj, bool decrefrefs, bool freenonrefs)
{
	assert(rawobj->type->kind == TYPE_ASDACLASS);
	AsdaInstObject *obj = (AsdaInstObject *) rawobj;

	if (decrefrefs) {
		// asda attrs are first in obj->type->attrs
		for (size_t i = 0; i < ((struct TypeAsdaClass *)obj->type)->nasdaattrs; i++) {
			assert(obj->type->attrs[i].kind == TYPE_ATTR_ASDA);
			OBJECT_DECREF(obj->attrvals[i]);
		}
	}

	if (freenonrefs)
		free(obj->attrvals);
}

Object *asdainstobj_constructor(Interp *interp, const struct Type *type, struct Object *const *args, size_t nargs)
{
	assert(type->kind == TYPE_ASDACLASS);
	struct TypeAsdaClass *tac = (struct TypeAsdaClass *) type;

	struct Object **av = calloc(tac->nasdaattrs, sizeof(av[0]));   // av = attr vals = attribute values
	if (tac->nasdaattrs && !av) {
		errobj_set_nomem(interp);
		return NULL;
	}

	AsdaInstObject *obj = object_new(interp, type, destroy_asda_instance, sizeof(*obj));
	if (!obj) {
		free(av);
		return NULL;
	}

	assert(nargs <= tac->nasdaattrs);
	memcpy(av, args, sizeof(av[0]) * nargs);
	for (size_t i = 0; i < nargs; i++)
		OBJECT_INCREF(av[i]);

	obj->attrvals = av;
	return (Object *)obj;
}
