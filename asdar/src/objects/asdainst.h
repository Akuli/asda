// instances of classes defined in asda

#ifndef ASDACLASS_H
#define ASDACLASS_H

#include <stddef.h>
#include "../interp.h"
#include "../object.h"
#include "../type.h"

typedef struct AsdaInstObject {
	OBJECT_HEAD
	struct Object **attrvals;   // the number of these is in the ->type
} AsdaInstObject;

// used in ../type.c
Object *asdainstobj_constructor(Interp *interp, const struct Type *type, struct Object *const *args, size_t nargs);

#endif   // ASDACLASS_H
