#include "string.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "../utf8.h"


struct StringData {
	uint32_t *val;
	size_t len;
};

static void stringdata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
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
		interp_errstr_nomem(interp);
		return NULL;
	}
	strdat->val = val;
	strdat->len = len;

	return object_new(interp, &stringobj_type, (struct ObjData){
		.val = strdat,
		.destroy = stringdata_destroy,
	});
}

struct Object *stringobj_new(struct Interp *interp, const uint32_t *val, size_t len)
{
	uint32_t *valcp = malloc(sizeof(uint32_t)*len);
	if (!valcp) {
		interp_errstr_nomem(interp);
		return NULL;
	}
	return stringobj_new_nocpy(interp, valcp, len);
}

struct Object *stringobj_new_utf8(struct Interp *interp, const char *utf, size_t utflen)
{
	uint32_t *uni;
	size_t unilen;
	if (!utf8_decode(interp, utf, utflen, &uni, &unilen))
		return NULL;
	return stringobj_new_nocpy(interp, uni, unilen);
}


// TODO: add methods
const struct Type stringobj_type = { .attribs = NULL, .nattribs = 0 };
