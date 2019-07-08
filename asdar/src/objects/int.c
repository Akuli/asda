#include <assert.h>
#include <gmp.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "../interp.h"
#include "../objtyp.h"
#include "err.h"
#include "func.h"
#include "int.h"
#include "string.h"

struct IntData {
	/** Represents if the IntData has "spilled", i.e. > LONG_MAX || LONG_MIN */
	bool spilled;

	union {
		long val;
		mpz_t mpz;
	};

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
		if (data->spilled) mpz_clear(data->mpz);
		free(data);
	}
}


// will clear the mpz_t (immediately on error, otherise when returned object is destroyed)
static Object *new_from_mpzt(Interp *interp, mpz_t mpz)
{
	if (mpz_fits_sint_p(mpz)) {
		long value = mpz_get_si(mpz);
		mpz_clear(mpz);
		return intobj_new_long(interp, value);
	}

	int cacheidx;
	if (mpz_sgn(mpz) >= 0 && mpz_cmp_ui(mpz, sizeof(interp->intcache)/sizeof(interp->intcache[0])) < 0)
		cacheidx = (int)mpz_get_ui(mpz);
	else
		cacheidx = -1;

	if (cacheidx != -1 && interp->intcache[cacheidx]) {
		mpz_clear(mpz);
		OBJECT_INCREF(interp->intcache[cacheidx]);
		return interp->intcache[cacheidx];
	}

	struct IntData *data = malloc(sizeof *data);
	if(!data) {
		mpz_clear(mpz);
		errobj_set_nomem(interp);
		return NULL;
	}

	data->spilled = true;

	/* XXX: is this safe at all? do we know where data->mpz points to? isn't it
	 * initialized memory? */
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
	long cacheidx;
	if (l >= 0 && (size_t)l < sizeof(interp->intcache)/sizeof(interp->intcache[0])) {
		cacheidx = l;

		if (interp->intcache[cacheidx]) {
			OBJECT_INCREF(interp->intcache[cacheidx]);
			return interp->intcache[cacheidx];
		}
	} else {
		cacheidx = -1;
	}

	struct IntData *data = malloc(sizeof *data);
	if(!data) {
		errobj_set_nomem(interp);
		return NULL;
	}

	data->spilled = false;
	data->val = l;
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

Object *intobj_new_bebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate)
{
	mpz_t mpz;
	mpz_init(mpz);
	mpz_import(
		mpz,
		len,
		1, // order; whole-array endianness
		1, // size; Size of `seq` element in bytes
		0, // endian; per-element endianness
		0, // nails; bits-per-element to skip
		seq
	);

	if(negate)
		mpz_neg(mpz, mpz);

	return new_from_mpzt(interp, mpz);
}

int intobj_cmp(Object *x, Object *y)
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);

	struct IntData *x_data = (struct IntData*) x->data.val;
	struct IntData *y_data = (struct IntData*) y->data.val;

	if (!x_data->spilled && !y_data->spilled) {
		/* https://stackoverflow.com/a/10997428 */
		return (x_data->val > y_data->val) - (x_data->val < y_data->val);
	} else if (x_data->spilled && !y_data->spilled) {
		return mpz_cmp_si(x_data->mpz, y_data->val);
	} else if (!x_data->spilled && y_data->spilled) {
		return -mpz_cmp_si(y_data->mpz, x_data->val);
	} else {
		return mpz_cmp( x_data->mpz, y_data->mpz );
	}
}

int intobj_cmp_long(Object *x, long y)
{
	assert(x->type == &intobj_type);
	struct IntData *data = (struct IntData*) x->data.val;

	if (data->spilled) {
		return mpz_cmp_si( ((struct IntData*)x->data.val)->mpz, y );
	} else {
		return (data->val > y) - (data->val < y);
	}
}

static void intobj_spill(Object *obj) {
	assert(obj->type == &intobj_type);

	struct IntData *data = (struct IntData*) obj->data.val;

	assert(!data->spilled);

	mpz_t mpz;
	mpz_init_set_si(mpz, data->val);

	data->spilled = true;
	*data->mpz = *mpz;
}

/* https://stackoverflow.com/a/2633929 */
#define ADD_WOULD_OVERFLOW(x, y) ((y > 0 && x > LONG_MAX - y) || (y < 0 && x < LONG_MIN - y))

/* https://stackoverflow.com/a/7684078 */
#define MUL_WOULD_OVERFLOW(a, b) (!((b > 0 && a <= INT_MAX / b && a >= INT_MIN / b) || (b == 0) || (b == -1 && a >= -INT_MAX) || (b < -1 && a >= INT_MAX / b && a <= INT_MIN / b)))

Object *intobj_add(Interp *interp, Object *x, Object *y)
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);

	struct IntData *x_data = (struct IntData*) x->data.val;
	struct IntData *y_data = (struct IntData*) y->data.val;

	if (!x_data->spilled && !y_data->spilled) {
		if (ADD_WOULD_OVERFLOW(x_data->val, y_data->val)) {
			intobj_spill(x);
		} else {
			return intobj_new_long(interp, x_data->val + y_data->val);
		}
	}

	mpz_t res;
	mpz_init(res);

	if (x_data->spilled && y_data->spilled) {
		mpz_add(res, x_data->mpz, y_data->mpz);
	} else {
		if (!x_data->spilled && y_data->spilled) { \
			void *tmp = x_data;
			x_data = y_data;
			y_data = tmp;
		}

		if (y_data->val > 0) mpz_add_ui(res, x_data->mpz, (unsigned long) y_data->val);
		else mpz_sub_ui(res, x_data->mpz, (unsigned long) -y_data->val);
	}

	return new_from_mpzt(interp, res);
}

Object *intobj_sub(Interp *interp, Object *x, Object *y)
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);

	struct IntData *x_data = (struct IntData*) x->data.val;
	struct IntData *y_data = (struct IntData*) y->data.val;

	if (!x_data->spilled && !y_data->spilled) {
		/* https://stackoverflow.com/a/2633929 */
		if (ADD_WOULD_OVERFLOW(x_data->val, -y_data->val)) {
			intobj_spill(x);
		} else {
			return intobj_new_long(interp, x_data->val - y_data->val);
		}
	}

	mpz_t res;
	mpz_init(res);

	if (x_data->spilled && y_data->spilled) {
		mpz_add(res, x_data->mpz, y_data->mpz);
	} else {
		bool swapped = false;
		if (!x_data->spilled && y_data->spilled) {
			void *tmp = x_data;
			x_data = y_data;
			y_data = tmp;
			swapped = true;
		}

		if (y_data->val > 0) mpz_sub_ui(res, x_data->mpz, (unsigned long) y_data->val);
		else mpz_add_ui(res, x_data->mpz, (unsigned long) -y_data->val);

		if (swapped) mpz_neg(res, res);
	}

	return new_from_mpzt(interp, res);
}

Object *intobj_mul(Interp *interp, Object *x, Object *y)
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);

	struct IntData *x_data = (struct IntData*) x->data.val;
	struct IntData *y_data = (struct IntData*) y->data.val;

	if (!x_data->spilled && !y_data->spilled) {
		if (x_data->val != 0 && y_data->val != 0 && MUL_WOULD_OVERFLOW(x_data->val, y_data->val)) {
			intobj_spill(x);
		} else {
			return intobj_new_long(interp, x_data->val * y_data->val);
		}
	}

	mpz_t res;
	mpz_init(res);

	if (x_data->spilled && y_data->spilled) {
		mpz_add(res, x_data->mpz, y_data->mpz);
	} else {
		if (!x_data->spilled && y_data->spilled) { \
			void *tmp = x_data;
			x_data = y_data;
			y_data = tmp;
		}

		mpz_mul_si(res, x_data->mpz, y_data->val);
	}

	return new_from_mpzt(interp, res);
}


Object *intobj_neg(Interp *interp, Object *x)
{
	assert(x->type == &intobj_type);

	struct IntData *data = x->data.val;

	if (data->spilled) {
		mpz_t res;
		mpz_init(res);
		mpz_neg(res, data->mpz);
		return new_from_mpzt(interp, res);
	} else {
		return intobj_new_long(interp, -data->val);
	}
}

// this does NOT return a new reference, you need to incref
static Object *get_string_object(Interp *interp, Object *x)
{
	assert(x->type == &intobj_type);
	struct IntData *id = x->data.val;

	if (!id->str) {
		char *str;

		if (id->spilled) {
			// +2 is explained in mpz_get_str docs
			str = malloc(mpz_sizeinbase(id->mpz, 10) + 2);
			if (!str) {
				errobj_set_nomem(interp);
				return NULL;
			}
			mpz_get_str(str, 10, id->mpz);
		} else {
			/* https://stackoverflow.com/questions/8257714/how-to-convert-an-int-to-string-in-c#comment45289620_8257728 */
			int len = snprintf(NULL, 0, "%ld", id->val);
			assert(len > 0);
			str = malloc(((size_t)len + 1) * sizeof(char));
			sprintf(str, "%ld", id->val);
		}

		id->str = stringobj_new_utf8(interp, str, strlen(str));   // may be NULL
		free(str);
	}

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

static bool tostring_impl(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	assert(nargs == 1);

	Object *obj = get_string_object(interp, args[0]);
	if (!obj)
		return false;
	OBJECT_INCREF(obj);
	*result = obj;
	return true;
}

static struct FuncObjData tostringdata = FUNCOBJDATA_COMPILETIMECREATE(tostring_impl);
static Object tostring = OBJECT_COMPILETIMECREATE(&funcobj_type, &tostringdata);

static Object *methods[] = { &tostring };

const struct Type intobj_type = { .methods = methods, .nmethods = sizeof(methods)/sizeof(methods[0]) };
