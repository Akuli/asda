#include <assert.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <gmp.h>

#include "../interp.h"
#include "../object.h"
#include "../type.h"
#include "err.h"
#include "func.h"
#include "int.h"
#include "string.h"

/*
checks that long is 2's complement, i.e. abs(LONG_MIN) == LONG_MAX + 1
this is needed because the code assumes that if x is a long, then -x
	- doesn't fit in a long, if x == LONG_MIN
	- fits in a long, if x != LONG_MIN

suppor for other systems can be added later
*/
#if LONG_MIN + LONG_MAX != -1
# error "your system is unsupported, a two's complement long is needed"
#endif

/*
this code assigns mpz_t's to each other like this

	*mpz1 = *mpz2

it works because mpz_t is an array of 1 element
I don't know whether that is documented
*/

// TODO: this code has a LOT of ifs... add tests for most things


static void destroy_intobj(Object *obj, bool decrefrefs, bool freenonrefs)
{
	IntObject *x = (IntObject *)obj;
	if (decrefrefs) {
		if (x->str)
			OBJECT_DECREF(x->str);
	}
	if (freenonrefs) {
		if (x->spilled) mpz_clear(x->val.mpz);
	}
}


IntObject *intobj_new_long(Interp *interp, long l)
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

	IntObject *obj = object_new(interp, &intobj_type, destroy_intobj, sizeof(*obj));
	if (!obj)
		return NULL;

	obj->spilled = false;
	obj->val.lon = l;
	obj->str = NULL;

	if (cacheidx != -1) {
		interp->intcache[cacheidx] = obj;
		OBJECT_INCREF(obj);
	}
	return obj;
}

// will clear the mpz_t (immediately on error, otherise when returned object is destroyed)
static IntObject *new_from_mpzt(Interp *interp, mpz_t mpz)
{
	if (mpz_fits_slong_p(mpz)) {
		long value = mpz_get_si(mpz);
		mpz_clear(mpz);
		return intobj_new_long(interp, value);
	}

	IntObject *obj = object_new(interp, &intobj_type, destroy_intobj, sizeof(*obj));
	if (!obj) {
		mpz_clear(mpz);
		return NULL;
	}

	obj->spilled = true;
	*obj->val.mpz = *mpz;
	obj->str = NULL;
	return obj;
}

IntObject *intobj_new_lebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate)
{
	mpz_t mpz;
	mpz_init(mpz);
	mpz_import(
		mpz,
		len,
		-1, // order; whole-array endianness
		1, // size; Size of `seq` element in bytes
		0, // endian; per-element endianness
		0, // nails; bits-per-element to skip
		seq
	);

	if(negate)
		mpz_neg(mpz, mpz);

	return new_from_mpzt(interp, mpz);
}

int intobj_cmp(IntObject *x, IntObject *y)
{
	if (x == y)
		return 0;
	if (!x->spilled && !y->spilled) {
		/* https://stackoverflow.com/a/10997428 */
		return (x->val.lon > y->val.lon) - (x->val.lon < y->val.lon);
	} else if (x->spilled && !y->spilled) {
		return mpz_cmp_si(x->val.mpz, y->val.lon);
	} else if (!x->spilled && y->spilled) {
		return -mpz_cmp_si(y->val.mpz, x->val.lon);
	} else {
		return mpz_cmp( x->val.mpz, y->val.mpz );
	}
}

int intobj_cmp_long(IntObject *x, long y)
{
	if (x->spilled) {
		return mpz_cmp_si(x->val.mpz, y);
	} else {
		return (x->val.lon > y) - (x->val.lon < y);
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
static void add_signedlong_mpz(mpz_t res, const mpz_t x, long y)   // x + y
{
	if (y >= 0) mpz_add_ui(res, x, (unsigned long)y);
	else mpz_sub_ui(res, x, NEGATIVE_LONG_TO_ULONG(y));
}

static void sub_signedlong_mpz(mpz_t res, const mpz_t x, long y)   // x - y
{
	if (y >= 0) mpz_sub_ui(res, x, (unsigned long)y);
	else mpz_add_ui(res, x, NEGATIVE_LONG_TO_ULONG(y));
}

static void mul_signedlong_mpz(mpz_t res, const mpz_t x, long y)   // x * y
{
	if (y >= 0) mpz_mul_ui(res, x, (unsigned long)y);
	else {
		mpz_mul_ui(res, x, NEGATIVE_LONG_TO_ULONG(y));
		mpz_neg(res, res);
	}
}

static long add_longs(long x, long y) { return x + y; }
static long sub_longs(long x, long y) { return x - y; }
static long mul_longs(long x, long y) { return x * y; }

static IntObject *do_some_operation(Interp *interp, IntObject *x, IntObject *y,
	void (*mpzmpzfunc)(mpz_t, const mpz_t, const mpz_t),
	void (*mpzlongfunc)(mpz_t, const mpz_t, long),
	long (*longlongfunc)(long, long),
	bool (*overflowfunc)(long, long),
	void (*commutefunc)(mpz_t, const mpz_t)   // applying this to 'x OP y' gives 'y OP x'
)
{
	mpz_t res;

	if (!x->spilled && !y->spilled) {
		if (!overflowfunc(x->val.lon, y->val.lon))
			return intobj_new_long(interp, longlongfunc(x->val.lon, y->val.lon));

		mpz_init_set_si(res, x->val.lon);
		mpzlongfunc(res, res, y->val.lon);
	} else {
		mpz_init(res);

		if (x->spilled && y->spilled)
			mpzmpzfunc(res, x->val.mpz, y->val.mpz);

		else if (x->spilled && !y->spilled)
			mpzlongfunc(res, x->val.mpz, y->val.lon);

		else if (!x->spilled && y->spilled) {
			mpzlongfunc(res, y->val.mpz, x->val.lon);
			if (commutefunc)
				commutefunc(res, res);
		}

		else
			assert(0);
	}

	return new_from_mpzt(interp, res);
}

IntObject *intobj_add(Interp *interp, IntObject *x, IntObject *y) {
	return do_some_operation(interp, x, y, mpz_add, add_signedlong_mpz, add_longs, add_would_overflow, NULL);
}

IntObject *intobj_sub(Interp *interp, IntObject *x, IntObject *y) {
	return do_some_operation(interp, x, y, mpz_sub, sub_signedlong_mpz, sub_longs, sub_would_overflow, mpz_neg);
}

IntObject *intobj_mul(Interp *interp, IntObject *x, IntObject *y) {
	return do_some_operation(interp, x, y, mpz_mul, mul_signedlong_mpz, mul_longs, mul_would_overflow, NULL);
}


IntObject *intobj_neg(Interp *interp, IntObject *x)
{
	mpz_t res;

	if (x->spilled) {
		mpz_init(res);
		mpz_neg(res, x->val.mpz);
	}
	else if (x->val.lon == LONG_MIN)
		mpz_init_set_ui(res, NEGATIVE_LONG_TO_ULONG(LONG_MIN));
	else
		return intobj_new_long(interp, -x->val.lon);

	return new_from_mpzt(interp, res);
}


// this does NOT return a new reference, you need to incref
static StringObject *get_string_object(Interp *interp, IntObject *x)
{
	if (x->str)
		return x->str;

	char *str;
	char buf[100];   // enough for a long, but not for an mpz

	if (x->spilled) {
		// +2 is explained in mpz_get_str docs
		str = malloc(mpz_sizeinbase(x->val.mpz, 10) + 2);
		if (!str) {
			errobj_set_nomem(interp);
			return NULL;
		}
		mpz_get_str(str, 10, x->val.mpz);
	} else {
		sprintf(buf, "%ld", x->val.lon);
		str = buf;
	}

	x->str = stringobj_new_utf8(interp, str, strlen(str));   // may be NULL
	if (str != buf)
		free(str);
	return x->str;   // may be NULL
}

const char *intobj_tocstr(Interp *interp, IntObject *x)
{
	StringObject *obj = get_string_object(interp, x);
	if (!obj)
		return NULL;

	const char *res;
	size_t junk;
	if (!stringobj_toutf8(obj, &res, &junk))
		return NULL;
	return res;
}

static bool tostring_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	IntObject *x = (IntObject *)args[0];

	StringObject *obj = get_string_object(interp, x);
	if (!obj)
		return false;

	OBJECT_INCREF(obj);
	*result = (Object *)obj;
	return true;
}
FUNCOBJ_COMPILETIMECREATE(tostring, &stringobj_type, { &intobj_type });

static FuncObject *methods[] = { &tostring };
const struct Type intobj_type = TYPE_BASIC_COMPILETIMECREATE(methods, sizeof(methods)/sizeof(methods[0]));
