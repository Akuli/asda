#include "builtin.h"
#include <stdbool.h>
#include <stdio.h>
#include "interp.h"
#include "object.h"
#include "type.h"
#include "objects/array.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/int.h"
#include "objects/string.h"


const struct Type* const builtin_types[] = {
	&stringobj_type,
	&intobj_type,
	&boolobj_type,
	&type_object,
	&errobj_type_error,
	&errobj_type_nomem,
	&errobj_type_variable,
	&errobj_type_value,
	&errobj_type_os,
	&arrayobj_type,
};
const size_t builtin_ntypes = sizeof(builtin_types)/sizeof(builtin_types[0]);
