#include "func.h"
#include <assert.h>
#include <stdbool.h>
#include "../interp.h"
#include "../objtyp.h"


const struct Type funcobj_type_ret = {
	.attribs = NULL,
	.nattribs = 0,
};
const struct Type funcobj_type_noret = {
	.attribs = NULL,
	.nattribs = 0,
};


bool funcobj_call_noret(
	struct Interp *interp, struct Object *f, struct Object **args, size_t nargs)
{
	assert(f->type == &funcobj_type_noret);
	struct FuncObjData *fod = f->data.val;
	return fod->cfunc.noret(interp, args, nargs);
}

struct Object* funcobj_call_ret(
	struct Interp *interp, struct Object *f, struct Object **args, size_t nargs)
{
	assert(f->type == &funcobj_type_ret);
	struct FuncObjData *fod = f->data.val;
	return fod->cfunc.ret(interp, args, nargs);
}
