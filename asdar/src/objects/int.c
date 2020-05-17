// TODO: tests

#include "int.h"

#include <assert.h>
#include <limits.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <gmp.h>

#include "../interp.h"
#include "../object.h"
#include "bool.h"
#include "err.h"
#include "string.h"

/*
Welcome to this mess, feels nice and evil... muhaha >xD

Small integers are not malloced. Instead, we assume that all integer pointers have
last bit set to 0, and we set that to 1 for small integers using rest of the bits
for an integer value. This is called tagged pointer, although our tagged "pointers"
don't actually point to anything.

So, we have 3 kinds of integer objects:
- Small integer objects (i.e. integer objects with that last bit set to 1)
- Big integer objects that fit in a long
- Big integer objects that don't fit in a long

We use long to represent small numbers. It would be nice to use intptr_t for that,
but GMP has handy functions for working with longs.
*/
static_assert(sizeof(long) >= sizeof(intptr_t), "sorry, your system is not supported");

#define IS_SMALL(OBJ) ( ((intptr_t)(OBJ)) & 1 )
bool intobj_fits2long(IntObject *x) { return IS_SMALL(x) || mpz_fits_slong_p(x->mpz); }

/*
We use intptr_t to represent small integers, but we need to encode them into some
odd number, because odd numbers have last bit 1, and even numbers have last bit 0.
We do that by encoding a small integer n to 2n+1.
*/
static inline IntObject *encode(long n)
{
	return (IntObject *)(intptr_t)( 2L*n + 1L );
}

static inline long decode(IntObject *ptr)
{
	assert(IS_SMALL(ptr));
	return ((long)(intptr_t)ptr - 1L)/2L;
}

/*
Calculating (INTPTR_MAX - 1)/2 does the right thing because / floors positive
numbers; this means that our max might end up a little small, which is fine. That
can even be encoded, because for positive x we have (x/2)*2 <= x, so no step of
encode((INTPTR_MAX - 1)/2) overflows (choose x = INTPTR_MAX - 1). So we could do
this:

	#define SMALL_MAX ( ((long)INTPTR_MAX - 1L)/2L )

We already checked that sizeof(long) >= sizeof(intptr_t), so casting intptr_t to
long should work.

For minimums, we can't subtract 1 from the most negative allowed number. We could
calculate (INTPTR_MIN - 1)/2 without underflow, but it might not be possible to
encode that because calculating ((INTPTR_MIN - 1)/2)*2 could underflow. Because /
rounds toward zero, we have (INTPTR_MIN/2)*2 >= INTPTR_MIN and we can encode
INTPTR_MIN/2. So, we could do this:

	#define SMALL_MIN ( ((long)INTPTR_MIN)/2L )

However, it's handy to negate small numbers by putting minuses in front of them.
We want to ensure that doing that always gives a small number. This means that we
need SMALL_MIN = -SMALL_MAX.
*/
#define min(a, b) ((a)<(b) ? (a) : (b))
#define SMALL_MAX min( ((long)INTPTR_MAX - 1L)/2L, -( ((long)INTPTR_MIN)/2L ) )
#define SMALL_MIN (-SMALL_MAX)

/*
We need to assign mpz_t's to each other. I didn't find a documented way to do that,
but mpz_t is an array type containing one struct element.
*/
#define ASSIGN_MPZ(to, from) *(to) = *(from)


static void destroy_intobj(Object *obj, bool decrefrefs, bool freenonrefs)
{
	IntObject *x = (IntObject *)obj;
	if (decrefrefs && x->strobj)
		OBJECT_DECREF(x->strobj);
	if (freenonrefs)
		mpz_clear(x->mpz);
}

// always clears mpz
static IntObject *new_from_mpzt(Interp *interp, mpz_t mpz)
{
	if (mpz_fits_slong_p(mpz)) {
		long val = mpz_get_si(mpz);
		if (SMALL_MIN <= val && val <= SMALL_MAX) {
			mpz_clear(mpz);
			return encode(val);
		}
	}

	IntObject *obj = object_new(interp, destroy_intobj, sizeof(*obj));
	if (!obj) {
		mpz_clear(mpz);
		return NULL;
	}

	ASSIGN_MPZ(obj->mpz, mpz);
	obj->strobj = NULL;
	return obj;
}

IntObject *intobj_new_long(Interp *interp, long val)
{
	if (SMALL_MIN <= val && val <= SMALL_MAX)
		return encode(val);

	mpz_t mpz;
	mpz_init_set_si(mpz, val);
	return new_from_mpzt(interp, mpz);
}

IntObject *intobj_new_lebytes(Interp *interp, const unsigned char *seq, size_t len, bool negate)
{
	// this could be optimized more by checking whether it fits to a small intobj
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

long intobj_getlong(IntObject *x)
{
	if (IS_SMALL(x))
		return decode(x);

	assert(mpz_fits_slong_p(x->mpz));
	return mpz_get_si(x->mpz);
}

int intobj_cmp(IntObject *x, IntObject *y)
{
	if (x == y)
		return 0;

	/* https://stackoverflow.com/a/10997428 */
	if (IS_SMALL(x) && IS_SMALL(y))
		return (decode(x) > decode(y)) - (decode(x) < decode(y));

	if (!IS_SMALL(x) && IS_SMALL(y))
		return mpz_cmp_si(x->mpz, decode(y));

	if (IS_SMALL(x) && !IS_SMALL(y))
		return -mpz_cmp_si(y->mpz, decode(x));

	return mpz_cmp(x->mpz, y->mpz);
}

int intobj_cmp_long(IntObject *x, long y)
{
	if (IS_SMALL(x))
		return (decode(x) > y) - (decode(x) < y);
	return mpz_cmp_si(x->mpz, y);
}


// -LONG_MIN fits in unsigned long
// -LONG_MIN doesn't fit in a long, but -(LONG_MIN+1) does
#define NEGATIVE_LONG_TO_ULONG(x) ( ((unsigned long) -((x)+1L)) + 1UL )


/*
overflow checks borrowed from stackoverflow, with min and max values replaced by
SMALL_MIN and SMALL_MAX

https://stackoverflow.com/a/2633929
https://stackoverflow.com/a/59973714
https://stackoverflow.com/a/7684078

all bla_stays_small functions assume that x and y are small
*/

static bool add_stays_small(long x, long y)
{
	return !(y > 0 && x > SMALL_MAX - y) && !(y < 0 && x < SMALL_MIN - y);
}

static bool sub_stays_small(long x, long y)
{
	return !(y > 0 && x < SMALL_MIN + y) && !(y < 0 && x > SMALL_MAX + y);
}

static bool mul_stays_small(long x, long y)
{
	return (y > 0 && x <= SMALL_MAX / y && x >= SMALL_MIN / y)
		|| (y == 0)
		|| (y == -1 && x >= -SMALL_MAX)
		|| (y < -1 && x >= SMALL_MAX / y && x <= SMALL_MIN / y);
}

// there is no mpz_add_si, mpz_sub_si, mpz_mul_si
// these assume that -y fits into a long, which is fine because y is small
static void add_signedlong_mpz(mpz_t res, const mpz_t x, long y)   // x + y
{
	if (y >= 0)
		mpz_add_ui(res, x, (unsigned long)y);
	else
		mpz_sub_ui(res, x, (unsigned long)-y);
}

static void sub_signedlong_mpz(mpz_t res, const mpz_t x, long y)   // x - y
{
	if (y >= 0)
		mpz_sub_ui(res, x, (unsigned long)y);
	else
		mpz_add_ui(res, x, (unsigned long)-y);
}

static void mul_signedlong_mpz(mpz_t res, const mpz_t x, long y)   // x * y
{
	mpz_mul_ui(res, x, (unsigned long) labs(y));
	if (y < 0)
		mpz_neg(res, res);
}

static long add_longs(long x, long y) { return x + y; }
static long sub_longs(long x, long y) { return x - y; }
static long mul_longs(long x, long y) { return x * y; }

static IntObject *do_some_operation(Interp *interp, IntObject *x, IntObject *y,
	void (*mpzmpzfunc)(mpz_t, const mpz_t, const mpz_t),
	void (*mpzsmallfunc)(mpz_t, const mpz_t, long),
	long (*smallsmallfunc)(long, long),
	bool (*staysmall)(long, long),
	void (*commutefunc)(mpz_t, const mpz_t)   // applying this to 'x OP y' gives 'y OP x'
)
{
	mpz_t res;

	if (IS_SMALL(x) && IS_SMALL(y)) {
		if (staysmall(decode(x), decode(y)))
			return encode(smallsmallfunc(decode(x), decode(y)));

		mpz_init_set_si(res, decode(x));
		mpzsmallfunc(res, res, decode(y));
	} else {
		mpz_init(res);

		if (IS_SMALL(y)) {
			mpzsmallfunc(res, x->mpz, decode(y));
		} else if (IS_SMALL(x)) {
			mpzsmallfunc(res, y->mpz, decode(x));
			if (commutefunc)
				commutefunc(res, res);
		} else {
			mpzmpzfunc(res, x->mpz, y->mpz);
		}
	}

	return new_from_mpzt(interp, res);
}


IntObject *intobj_add(Interp *interp, IntObject *x, IntObject *y) {
	return do_some_operation(interp, x, y, mpz_add, add_signedlong_mpz, add_longs, add_stays_small, NULL);
}

IntObject *intobj_sub(Interp *interp, IntObject *x, IntObject *y) {
	return do_some_operation(interp, x, y, mpz_sub, sub_signedlong_mpz, sub_longs, sub_stays_small, mpz_neg);
}

IntObject *intobj_mul(Interp *interp, IntObject *x, IntObject *y) {
	return do_some_operation(interp, x, y, mpz_mul, mul_signedlong_mpz, mul_longs, mul_stays_small, NULL);
}

IntObject *intobj_neg(Interp *interp, IntObject *x)
{
	if (IS_SMALL(x))
		return encode(-decode(x));

	mpz_t res;
	mpz_init(res);
	mpz_neg(res, x->mpz);
	return new_from_mpzt(interp, res);
}


/*
Converting to strings is a bit weird:
- For small integers, there is no cache converted strings
	- New cstr is created with sprintf every time it's needed (malloc not needed)
	- Figure out how to create cstr, then make all other functions do that
- For big integers, a StringObject is cached.
	- Never create cstr without StringObject
	- Figure out how to create StringObject, then make all other functions do that
*/

static void create_cstr_for_small(IntObject *smol, char *buf)
{
	assert(buf);
	sprintf(buf, "%ld", decode(smol));
}

static void try_to_create_stringobj_for_big(Interp *interp, IntObject *big)
{
	if (big->strobj)
		return;

	// mpz_get_str docs explain why +2
	char *str = malloc(mpz_sizeinbase(big->mpz, 10) + 2);
	if (!str) {
		errobj_set_nomem(interp);
		return;
	}

	mpz_get_str(str, 10, big->mpz);
	big->strobj = stringobj_new_nocp(interp, str, strlen(str));   // may be NULL
}


const char *intobj_tocstr(Interp *interp, IntObject *x, char *tmp)
{
	if (IS_SMALL(x)) {
		create_cstr_for_small(x, tmp);
		return tmp;
	}

	try_to_create_stringobj_for_big(interp, x);
	return x->strobj ? stringobj_getutf8(x->strobj) : NULL;
}

StringObject *intobj_tostrobj(Interp *interp, IntObject *x)
{
	if (IS_SMALL(x)) {
		char tmp[INTOBJ_TOCSTR_TMPSZ];
		create_cstr_for_small(x, tmp);
		return stringobj_new(interp, tmp, strlen(tmp));
	}

	try_to_create_stringobj_for_big(interp, x);
	if (x->strobj)
		OBJECT_INCREF(x->strobj);
	return x->strobj;   // may be NULL
}


static Object *plus_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) intobj_add(interp, (IntObject *) args[0], (IntObject *) args[1]);
}

static Object *minus_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) intobj_sub(interp, (IntObject *) args[0], (IntObject *) args[1]);
}

static Object *times_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) intobj_mul(interp, (IntObject *) args[0], (IntObject *) args[1]);
}

static Object *prefix_minus_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) intobj_neg(interp, (IntObject *) args[0]);
}

static Object *eq_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda( intobj_cmp((IntObject *) args[0], (IntObject *) args[1])==0 );
}

static Object *tostring_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) intobj_tostrobj(interp, (IntObject*) args[0]);
}

const struct CFunc intobj_cfuncs[] = {
	{ "Int+Int", 2, true, { .ret = plus_cfunc }},
	{ "Int-Int", 2, true, { .ret = minus_cfunc }},
	{ "Int*Int", 2, true, { .ret = times_cfunc }},
	{ "-Int", 1, true, { .ret = prefix_minus_cfunc }},
	{ "Int==Int", 2, true, { .ret = eq_cfunc }},
	{ "int_to_string", 1, true, { .ret = tostring_cfunc }},
	{0},
};
