#include "int.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <gmp.h>
#include "../interp.h"
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


struct Object *intobj_new_mpzt(struct Interp *interp, mpz_t mpz)
{
	struct IntData *data = malloc(sizeof *data);
	if(!data) {
		mpz_clear(mpz);
		return NULL;
	}

	// this might be relying on GMP's implementation details, but it works :D
	*data->mpz = *mpz;

	return object_new(interp, &intobj_type, (struct ObjData){
		.val = data,
		.destroy = intdata_destroy,
	});
}

// see mpz_import docs
#define BIG_ENDIAN 1

struct Object *intobj_new_bebytes(struct Interp *interp, const unsigned char *seq, size_t len, bool negate)
{
	mpz_t mpz;
	mpz_init(mpz);
	mpz_import(mpz, len, BIG_ENDIAN, 1, 0, 0, seq);
	if(negate)
		mpz_neg(mpz, mpz);
	return intobj_new_mpzt(interp, mpz);
}

#undef BIG_ENDIAN


static struct Object *tostring_impl(struct Interp *interp, struct Object **args, size_t nargs)
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
