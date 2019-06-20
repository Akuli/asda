#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "string.h"


struct StringData {
	uint32_t *val;
	size_t len;
};

static void stringobj_data_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct StringData *data = vpdata;
	if (freenonrefs) {
		free(data->val);
		free(data);
	}
}


struct Object *stringobj_new_nocpy(struct Interp *interp, uint32_t *val, size_t len)
{
	struct StringData *strdat=malloc(sizeof(*strdat));
	if(!strdat) {
		free(val);
		return NULL;
	}
	strdat->val = val;
	strdat->len = len;

	return object_new(interp, stringobj_type, (struct ObjData){
		.val = strdat,
		.destroy = stringobj_data_destroy,
	});
}

struct Object *stringobj_new(struct Interp *interp, const uint32_t *val, size_t len)
{
	uint32_t *valcp = malloc(sizeof(uint32_t)*len);
	if (!valcp)
		return NULL;
	return stringobj_new_nocpy(interp, valcp, len);
}


// TODO: add methods
static const struct Type stringobj_type_value = { .attribs = NULL, .nattribs = 0 };
const struct Type *const stringobj_type = &stringobj_type_value;
