#include <stdbool.h>
#include "box.h"


static void destroy_box(Object *obj, bool decrefrefs, bool freenonrefs)
{
	BoxObject *box = (BoxObject *) obj;
	if (decrefrefs)
		OBJECT_DECREF(box->val);
}


BoxObject *boxobj_new(Interp *interp)
{
	BoxObject *obj = object_new(interp, &boxobj_type, destroy_box, sizeof(*obj));
	if (!obj)
		return NULL;
	obj->val = NULL;
	return obj;
}

void boxobj_set(BoxObject *box, Object *val)
{
	if (box->val)
		OBJECT_DECREF(box->val);
	box->val = val;
	OBJECT_INCREF(val);
}

const struct Type boxobj_type = TYPE_BASIC_COMPILETIMECREATE(NULL, NULL, NULL, 0);
