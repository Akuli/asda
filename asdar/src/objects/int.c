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

/*
this code assigns mpz_t's to each other like this

	*mpz1 = *mpz2

it works because mpz_t is an array of 1 element
I don't know whether that is documented
*/


struct IntData {
	/** Represents if the IntData has "spilled", i.e. > LONG_MAX || LONG_MIN */
	bool spilled;

	union {
		long lon;
		mpz_t mpz;
	} val;

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
		if (data->spilled) mpz_clear(data->val.mpz);
		free(data);
	}
}


Object *intobj_new_long(Interp *interp, long l)
{
	long cacheidx;
	if (l >= 0 && (unsigned long)l < sizeof(interp->intcache)/sizeof(interp->intcache[0])) {
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
	data->val.lon = l;
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

// will clear the mpz_t (immediately on error, otherise when returned object is destroyed)
static Object *new_from_mpzt(Interp *interp, mpz_t mpz)
{
	if (mpz_fits_slong_p(mpz)) {
		long value = mpz_get_si(mpz);
		mpz_clear(mpz);
		return intobj_new_long(interp, value);
	}

	struct IntData *data = malloc(sizeof *data);
	if(!data) {
		mpz_clear(mpz);
		errobj_set_nomem(interp);
		return NULL;
	}

	data->spilled = true;
	*data->val.mpz = *mpz;
	data->str = NULL;

	return object_new(interp, &intobj_type, (struct ObjData){
		.val = data,
		.destroy = intdata_destroy,
	});
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
		return (x_data->val.lon > y_data->val.lon) - (x_data->val.lon < y_data->val.lon);
	} else if (x_data->spilled && !y_data->spilled) {
		return mpz_cmp_si(x_data->val.mpz, y_data->val.lon);
	} else if (!x_data->spilled && y_data->spilled) {
		return -mpz_cmp_si(y_data->val.mpz, x_data->val.lon);
	} else {
		return mpz_cmp( x_data->val.mpz, y_data->val.mpz );
	}
}

int intobj_cmp_long(Object *x, long y)
{
	assert(x->type == &intobj_type);
	struct IntData *data = (struct IntData*) x->data.val;

	if (data->spilled) {
		return mpz_cmp_si( ((struct IntData*)x->data.val)->val.mpz, y );
	} else {
		return (data->val.lon > y) - (data->val.lon < y);
	}
}


// -LONG_MIN fits in unsigned long
// -LONG_MIN doesn't fit in a long, but -(LONG_MIN+1) does
#define NEGATIVE_LONG_TO_ULONG(x) ( ((unsigned long) -((x)+1)) + 1 )


/* https://stackoverflow.com/a/2633929 */
static bool add_would_overflow(long x, long y) {
	return ((y > 0 && x > LONG_MAX - y) || (y < 0 && x < LONG_MIN - y));
}

static bool sub_would_overflow(long x, long y) {
	// -LONG_MIN doesn't work
	if (y == LONG_MIN)
		return (x > 0);   // TODO: think through this while being less tired than im now

	return add_would_overflow(x, -y);
}

/* https://stackoverflow.com/a/7684078 */
static bool mul_would_overflow(long a, long b) {
	return (!((b > 0 && a <= INT_MAX / b && a >= INT_MIN / b) || (b == 0) || (b == -1 && a >= -INT_MAX) || (b < -1 && a >= INT_MAX / b && a <= INT_MIN / b)));
}

// there is no mpz_add_si, mpz_sub_si, mpz_mul_si
static void add_signedlong_mpz(mpz_t res, long val)
{
	if (val >= 0)
		mpz_add_ui(res, res, (unsigned long)val);
	else
		mpz_sub_ui(res, res, NEGATIVE_LONG_TO_ULONG(val));
}

static void sub_signedlong_mpz(mpz_t res, long val)
{
	if (val >= 0)
		mpz_sub_ui(res, res, (unsigned long)val);
	else
		mpz_add_ui(res, res, NEGATIVE_LONG_TO_ULONG(val));
}

static void mul_signedlong_mpz(mpz_t res, long val)
{
	if (val >= 0) {
		mpz_mul_ui(res, res, (unsigned long)val);
	} else {
		mpz_mul_ui(res, res, NEGATIVE_LONG_TO_ULONG(val));
		mpz_neg(res, res);
	}
}

static long add_longs(long x, long y) { return x + y; }
static long sub_longs(long x, long y) { return x - y; }
static long mul_longs(long x, long y) { return x * y; }

static Object *do_some_operation(Interp *interp, Object *x, Object *y,
	void (*mpzmpzfunc)(mpz_t, const mpz_t, const mpz_t),
	void (*mpzlongfunc)(mpz_t, long),
	long (*longlongfunc)(long, long),
	bool (*overflowfunc)(long, long))
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);

	struct IntData *x_data = (struct IntData*) x->data.val;
	struct IntData *y_data = (struct IntData*) y->data.val;

	if (!x_data->spilled && !y_data->spilled && !overflowfunc(x_data->val.lon, y_data->val.lon))
		return intobj_new_long(interp, longlongfunc(x_data->val.lon, y_data->val.lon));

	mpz_t res;
	mpz_init(res);

	if (x_data->spilled)
		mpzmpzfunc(res, res, x_data->val.mpz);
	else
		mpzlongfunc(res, x_data->val.lon);

	if (y_data->spilled)
		mpzmpzfunc(res, res, y_data->val.mpz);
	else
		mpzlongfunc(res, y_data->val.lon);

	return new_from_mpzt(interp, res);
}

Object *intobj_add(Interp *interp, Object *x, Object *y) {
	return do_some_operation(interp, x, y, mpz_add, add_signedlong_mpz, add_longs, add_would_overflow);
}

Object *intobj_sub(Interp *interp, Object *x, Object *y) {
	return do_some_operation(interp, x, y, mpz_sub, sub_signedlong_mpz, sub_longs, sub_would_overflow);
}

Object *intobj_mul(Interp *interp, Object *x, Object *y) {
	return do_some_operation(interp, x, y, mpz_mul, mul_signedlong_mpz, mul_longs, mul_would_overflow);
}

Object *intobj_neg(Interp *interp, Object *x)
{
	assert(x->type == &intobj_type);

	struct IntData *data = x->data.val;

	if (data->spilled) {
		mpz_t res;
		mpz_init(res);
		mpz_neg(res, data->val.mpz);
		return new_from_mpzt(interp, res);
	} else {
		return intobj_new_long(interp, -data->val.lon);   // FIXME: -LONG_MIN bug
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
			str = malloc(mpz_sizeinbase(id->val.mpz, 10) + 2);
			if (!str) {
				errobj_set_nomem(interp);
				return NULL;
			}
			mpz_get_str(str, 10, id->val.mpz);
		} else {
			/* https://stackoverflow.com/questions/8257714/how-to-convert-an-int-to-string-in-c#comment45289620_8257728 */
			int len = snprintf(NULL, 0, "%ld", id->val.lon);
			assert(len > 0);
			str = malloc(((size_t)len + 1) * sizeof(char));
			sprintf(str, "%ld", id->val.lon);
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
