#include "string.h"
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include "../utf8.h"
#include "../interp.h"
#include "../objtyp.h"


struct StringData {
	uint32_t *val;
	size_t len;

	// don't use these directly, they are optimizations
	char *utf8cache;     // NULL for not cached
	size_t utf8cachelen;
};

static void stringdata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct StringData *data = vpdata;
	if (freenonrefs) {
		free(data->utf8cache);
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
	strdat->utf8cache = NULL;

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

bool stringobj_toutf8(struct Object *obj, const char **val, size_t *len)
{
	struct StringData *strdat = obj->data.val;
	if( !strdat->utf8cache &&
		!utf8_encode(obj->interp, strdat->val, strdat->len, &strdat->utf8cache, &strdat->utf8cachelen) )
	{
		strdat->utf8cache = NULL;
		return false;
	}

	*val = strdat->utf8cache;
	*len = strdat->utf8cachelen;
	return true;
}


// TODO: add methods
const struct Type stringobj_type = { .methods = NULL, .nmethods = 0 };
