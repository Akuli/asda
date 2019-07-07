#include "int.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <gmp.h>
#include "../interp.h"
#include "../objtyp.h"
#include "err.h"
#include "func.h"
#include "string.h"

struct IntData {
	mpz_t mpz;
	Object *str;   // string object, in base 10, NULL for not computed yet
};


static void intdata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct IntData *data = vpdata;
	if (decrefrefs) {
		if (data->str)
			OBJECT_DECREF(data->str);
	}
	if (freenonrefs) {
		mpz_clear(data->mpz);
		free(data);
	}
}


// will clear the mpz_t (immediately on error, otherise when returned object is destroyed)
static Object *new_from_mpzt(Interp *interp, mpz_t mpz)
{
	int cacheidx;
	if (0 <= mpz_cmp_ui(mpz, 0) &&
		mpz_cmp_ui(mpz, sizeof(interp->intcache)/sizeof(interp->intcache[0])) < 0)
	{
		cacheidx = (int)mpz_get_ui(mpz);
	} else {
		cacheidx = -1;
	}

	if (cacheidx != -1 && interp->intcache[cacheidx]) {
		OBJECT_INCREF(interp->intcache[cacheidx]);
		return interp->intcache[cacheidx];
	}

	struct IntData *data = malloc(sizeof *data);
	if(!data) {
		mpz_clear(mpz);
		errobj_set_nomem(interp);
		return NULL;
	}

	*data->mpz = *mpz;   // this might be relying on GMP's implementation details, but it works :D
	data->str = NULL;

	Object *res = object_new(interp, &intobj_type, (struct ObjData){
		.val = data,
		.destroy = intdata_destroy,
	});
	if (res != NULL && cacheidx != -1) {
		interp->intcache[cacheidx] = res;
		OBJECT_INCREF(res);
	}
	return res;
}

Object *intobj_new_long(Interp *interp, long l)
{
	mpz_t mpz;
	mpz_init_set_si(mpz, l);
	return new_from_mpzt(interp, mpz);
}

Object *intobj_new_bebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate)
{
	mpz_t mpz;
	mpz_init(mpz);
	mpz_import(mpz, len, 1, 1, 0, 0, seq);    // see docs for all the magic numbers
	if(negate)
		mpz_neg(mpz, mpz);
	return new_from_mpzt(interp, mpz);
}

int intobj_cmp(Object *x, Object *y)
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);
	return mpz_cmp( ((struct IntData*)x->data.val)->mpz, ((struct IntData*)y->data.val)->mpz );
}

int intobj_cmp_long(Object *x, long y)
{
	assert(x->type == &intobj_type);
	return mpz_cmp_si( ((struct IntData*)x->data.val)->mpz, y );
}


static Object *binary_operation(Interp *interp, Object *x, Object *y,
	void (*func)(mpz_t, const mpz_t, const mpz_t))
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);

	mpz_t res;
	mpz_init(res);
	func(res, ((struct IntData*)x->data.val)->mpz, ((struct IntData*)y->data.val)->mpz);
	return new_from_mpzt(interp, res);
}

Object *intobj_add(Interp *interp, Object *x, Object *y) { return binary_operation(interp, x, y, mpz_add); }
Object *intobj_sub(Interp *interp, Object *x, Object *y) { return binary_operation(interp, x, y, mpz_sub); }
Object *intobj_mul(Interp *interp, Object *x, Object *y) { return binary_operation(interp, x, y, mpz_mul); }

Object *intobj_neg(Interp *interp, Object *x)
{
	assert(x->type == &intobj_type);
	mpz_t res;
	mpz_init(res);
	mpz_neg(res, ((struct IntData*)x->data.val)->mpz);
	return new_from_mpzt(interp, res);
}

// this does NOT return a new reference, you need to incref
static Object *get_string_object(Interp *interp, Object *x)
{
	assert(x->type == &intobj_type);
	struct IntData *id = x->data.val;

	if (id->str)
		return id->str;

	// +2 is explained in mpz_get_str docs
	char *str = malloc(mpz_sizeinbase(id->mpz, 10) + 2);
	if (!str) {
		errobj_set_nomem(interp);
		return NULL;
	}
	mpz_get_str(str, 10, id->mpz);

	id->str = stringobj_new_utf8(interp, str, strlen(str));   // may be NULL
	free(str);
	return id->str;   // may be NULL
}

const char *intobj_tocstr(Interp *interp, Object *x)
{
	Object *obj = get_string_object(interp, x);
	if (!obj)
		return NULL;

	const char *res;
	size_t junk;
	if (!stringobj_toutf8(obj, &res, &junk))
		return NULL;
	return res;
}

static Object *tostring_impl(Interp *interp, struct ObjData data, Object *const *args, size_t nargs)
{
	assert(nargs == 1);

	Object *obj = get_string_object(interp, args[0]);
	if (!obj)
		return NULL;
	OBJECT_INCREF(obj);
	return obj;
}

static struct FuncObjData tostringdata = FUNCOBJDATA_COMPILETIMECREATE_RET(tostring_impl);
static Object tostring = OBJECT_COMPILETIMECREATE(&funcobj_type_ret, &tostringdata);

static Object *methods[] = { &tostring };

const struct Type intobj_type = { .methods = methods, .nmethods = sizeof(methods)/sizeof(methods[0]) };
