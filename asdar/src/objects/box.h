/*
wraps an object, wrapped object can be changed

useful for code like this:

	let n = 123
	let increment_n = () -> void:
		n = n + 1
	increment_n()
	print(n.to_string())

this puts 123 inside a box, and passes the box to the increment_n function with partial
*/

#ifndef OBJECTS_BOX_H
#define OBJECTS_BOX_H

#include "../interp.h"
#include "../object.h"
#include "../type.h"

extern const struct Type boxobj_type;

typedef struct BoxObject {
	OBJECT_HEAD
	Object *val;
} BoxObject;

BoxObject *boxobj_new(Interp *interp);
void boxobj_set(BoxObject *box, Object *val);

#endif   // OBJECTS_BOX_H
