#include "int.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <gmp.h>
#include "../interp.h"
#include "../objtyp.h"
#include "func.h"
#include "string.h"

struct IntData {
	mpz_t mpz;
};


static void intdata_destroy(void *vpdata, bool decrefrefs, bool freenonrefs)
{
	struct IntData *data = vpdata;
	if (freenonrefs) {
		mpz_clear(data->mpz);
		free(data);
	}
}


// will clear the mpz_t (immediately on error, otherise when returned object is destroyed)
static struct Object *new_from_mpzt(struct Interp *interp, mpz_t mpz)
{
	struct IntData *data = malloc(sizeof *data);
	if(!data) {
		mpz_clear(mpz);
		interp_errstr_nomem(interp);
		return NULL;
	}

	// this might be relying on GMP's implementation details, but it works :D
	*data->mpz = *mpz;

	return object_new(interp, &intobj_type, (struct ObjData){
		.val = data,
		.destroy = intdata_destroy,
	});
}

struct Object *intobj_new_bebytes(struct Interp *interp, const unsigned char *seq, size_t len, bool negate)
{
	mpz_t mpz;
	mpz_init(mpz);
	mpz_import(mpz, len, 1, 1, 0, 0, seq);    // see docs for all the magic numbers
	if(negate)
		mpz_neg(mpz, mpz);
	return new_from_mpzt(interp, mpz);
}


static struct Object *binary_operation(
	struct Interp *interp, struct Object *x, struct Object *y,
	void (*func)(mpz_t, const mpz_t, const mpz_t))
{
	assert(x->type == &intobj_type);
	assert(y->type == &intobj_type);

	mpz_t res;
	mpz_init(res);
	func(res, ((struct IntData*)x->data.val)->mpz, ((struct IntData*)y->data.val)->mpz);
	return new_from_mpzt(interp, res);
}

struct Object *intobj_add(struct Interp *interp, struct Object *x, struct Object *y) { return binary_operation(interp, x, y, mpz_add); }
struct Object *intobj_sub(struct Interp *interp, struct Object *x, struct Object *y) { return binary_operation(interp, x, y, mpz_sub); }
struct Object *intobj_mul(struct Interp *interp, struct Object *x, struct Object *y) { return binary_operation(interp, x, y, mpz_mul); }

struct Object *intobj_neg(struct Interp *interp, struct Object *x)
{
	assert(x->type == &intobj_type);
	mpz_t res;
	mpz_init(res);
	mpz_neg(res, ((struct IntData*)x->data.val)->mpz);
	return new_from_mpzt(interp, res);
}


static struct Object *tostring_impl(struct Interp *interp, struct ObjData data,
	struct Object *const *args, size_t nargs)
{
	assert(nargs == 1);
	assert(args[0]->type == &intobj_type);

	// I couldn't figure out how to assign an mpz_t to a local variable, but this works well enough
	struct IntData *id = args[0]->data.val;

	// +2 as documentation for mpz_get_str says: +1 for possible minus sign, +1 for 0 byte at end
	char *str = malloc(mpz_sizeinbase(id->mpz, 10) + 2);
	if(!str) {
		interp_errstr_nomem(interp);
		return NULL;
	}

	mpz_get_str(str, 10, id->mpz);

	struct Object *res = stringobj_new_utf8(interp, str, strlen(str));
	free(str);
	return res;   // may be NULL
}

static struct FuncObjData tostringdata = FUNCOBJDATA_COMPILETIMECREATE_RET(tostring_impl);
static struct Object tostring = OBJECT_COMPILETIMECREATE(&funcobj_type_ret, &tostringdata);

static struct Object *methods[] = { &tostring };

const struct Type intobj_type = { .methods = methods, .nmethods = sizeof(methods)/sizeof(methods[0]) };
