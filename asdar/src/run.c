#include "run.h"
#include <assert.h>
#include <stdio.h>
#include "builtin.h"
#include "code.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/string.h"


//#define DEBUG(...) printf(__VA_ARGS__)
#define DEBUG(...) (void)0

static void swap(Object **a, Object **b)
{
	Object *tmp = *a;
	*a = *b;
	*b = tmp;
}

// TODO: look into python's new vectorcall stuff
static bool call_builtin_function(Interp *interp, const struct BuiltinFunc *bfunc)
{
	assert(interp->objstack.len >= bfunc->nargs);
	assert(&builtin_funcs[0] <= bfunc && bfunc < &builtin_funcs[builtin_nfuncs]);

	bool ret = bfunc->ret;   // makes the compiler understand enough to not do warning
	Object **args = &interp->objstack.ptr[interp->objstack.len - bfunc->nargs];
	Object *retobj;
	bool ok;

	if (ret)
		ok = !!( retobj = bfunc->func.ret(interp, args) );
	else
		ok = bfunc->func.noret(interp, args);

	for (size_t i = 0; i < bfunc->nargs; i++)
		OBJECT_DECREF(args[i]);
	interp->objstack.len -= bfunc->nargs;

	if (!ok)
		return false;

	if (ret){
		if (!dynarray_push(interp, &interp->objstack, retobj)) {
			OBJECT_DECREF(retobj);
			return false;
		}
	}

	return true;
}

bool run(Interp *interp, size_t startidx)
{
	assert(interp->objstack.len == 0);
	const struct CodeOp *ptr = &interp->code.ptr[startidx];

	while(true){
		DEBUG("start=%p ptr=start+%p diff=%d\n",
			(void*)interp->code.ptr,
			(void*)ptr,
			(int)(ptr - interp->code.ptr));
		assert(interp->code.ptr <= ptr && ptr < &interp->code.ptr[interp->code.len]);

		size_t sz;
		Object *obj;

		switch(ptr->kind) {
		case CODE_FUNCBEGINS:
			sz = interp->objstack.len + ptr->data.objstackincr;
			if (!dynarray_alloc(interp, &interp->objstack, sz))
				goto error;
			ptr++;
			break;

		case CODE_CONSTANT:
			if (!dynarray_push(interp, &interp->objstack, ptr->data.obj))
				goto error;
			OBJECT_INCREF(ptr->data.obj);
			ptr++;
			break;

		case CODE_CALLBUILTINFUNC:
			if (!call_builtin_function(interp, ptr->data.builtinfunc))
				goto error;
			ptr++;
			break;

		case CODE_CALLCODEFUNC:
			if (!dynarray_push(interp, &interp->callstack, ptr))
				goto error;
			ptr = &interp->code.ptr[ptr->data.call.jump];
			break;

		case CODE_RETURN:
			if (interp->callstack.len == 0) {
				DEBUG("return and no more callstack, so we are done\n");
				assert(interp->objstack.len == 0);
				return true;
			}
			ptr = dynarray_pop(&interp->callstack) + 1;
			break;

		case CODE_SWAP:
			swap(
				&interp->objstack.ptr[interp->objstack.len - ptr->data.swap.index1 - 1],
				&interp->objstack.ptr[interp->objstack.len - ptr->data.swap.index2 - 1]);
			ptr++;
			break;

		case CODE_DUP:
			obj = interp->objstack.ptr[interp->objstack.len - ptr->data.objstackidx - 1];
			if (!dynarray_push(interp, &interp->objstack, obj))
				goto error;
			OBJECT_INCREF(obj);
			ptr++;
			break;

		case CODE_JUMPIF:
			obj = dynarray_pop(&interp->objstack);
			if (boolobj_asda2c((BoolObject *) obj))
				ptr = &interp->code.ptr[ptr->data.jump];
			else
				ptr++;
			OBJECT_DECREF(obj);
			break;

		default:
			printf("TODO: ");
			codeop_debug(ptr->kind);
			ptr++;
			break;
		}
	}

error:
	assert(0);  // TODO
}
