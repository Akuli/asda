#include "string.h"
#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include "func.h"
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
	if (len && !valcp) {   // malloc(0) is special
		interp_errstr_nomem(interp);
		return NULL;
	}

	memcpy(valcp, val, sizeof(uint32_t)*len);
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

struct Object *stringobj_join(struct Interp *interp, struct Object *const *strs, size_t nstrs)
{
	if(nstrs == 0)
		goto empty;
	if(nstrs == 1) {
		OBJECT_INCREF(strs[0]);
		return strs[0];
	}

	size_t lensum = 0;
	for (size_t i = 0; i < nstrs; i++)
		lensum += ((struct StringData *) strs[i]->data.val)->len;

	if(!lensum)
		goto empty;  // malloc(0) is special

	uint32_t *buf = malloc(sizeof(uint32_t)*lensum);
	if(!buf) {
		interp_errstr_nomem(interp);
		return NULL;
	}

	uint32_t *p = buf;
	for (size_t i = 0; i < nstrs; i++) {
		struct StringData *strdat = strs[i]->data.val;
		memcpy(p, strdat->val, sizeof(uint32_t)*strdat->len);
		p += strdat->len;
	}
	assert(p == buf + lensum);

	return stringobj_new_nocpy(interp, buf, lensum);

empty:
	return stringobj_new(interp, NULL, 0);
}


static struct Object *tostring_impl(struct Interp *interp, struct ObjData data, struct Object **args, size_t nargs)
{
	assert(nargs == 1);
	assert(args[0]->type == &stringobj_type);
	OBJECT_INCREF(args[0]);
	return args[0];
}

static struct FuncObjData tostringdata = FUNCOBJDATA_COMPILETIMECREATE_RET(tostring_impl);
static struct Object tostring = OBJECT_COMPILETIMECREATE(&funcobj_type_ret, &tostringdata);

// TODO: first string method should be uppercase
static struct Object *methods[] = { &tostring, &tostring };

const struct Type stringobj_type = { .methods = methods, .nmethods = sizeof(methods)/sizeof(methods[0]) };
