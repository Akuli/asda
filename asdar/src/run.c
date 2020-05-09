#include "run.h"
#include <stdio.h>
#include "code.h"
#include "objects/err.h"
#include "objects/string.h"


//#define DEBUG(...) printf(__VA_ARGS__)
#define DEBUG(...) (void)0

static bool print_string(Interp *interp, StringObject *str)
{
	const char *s;
	size_t len;
	if (!stringobj_toutf8(str, &s, &len))
		return false;

	printf("%.*s\n", (int)len, s);
	return true;
}

static void swap(Object **a, Object **b)
{
	Object *tmp = *a;
	*a = *b;
	*b = tmp;
}

bool run(Interp *interp, size_t startidx)
{
	DEBUG("how much code: %zu\n", interp->code.len);
	DEBUG("how much objstack: %zu\n", interp->objstack.len);
	const struct CodeOp *ptr = &interp->code.ptr[startidx];

	while(true){
		DEBUG("start=%p ptr=start+%p diff=%d\n",
			(void*)interp->code.ptr,
			(void*)ptr,
			(int)(ptr - interp->code.ptr));
		assert(interp->code.ptr <= ptr && ptr < &interp->code.ptr[interp->code.len]);

		size_t sz;
		Object *obj;
		bool ok;

		switch(ptr->kind) {
		case CODE_FUNCBEGINS:
			DEBUG("Function begins hurr durr %d\n", (int)ptr->data.objstackincr);
			sz = interp->objstack.len + ptr->data.objstackincr;
			if (!dynarray_alloc(interp, &interp->objstack, sz))
				goto error;
			ptr++;
			break;

		case CODE_CONSTANT:
			DEBUG("Constant hurr durr\n");
			if (!dynarray_push(interp, &interp->objstack, ptr->data.obj))
				goto error;
			OBJECT_INCREF(ptr->data.obj);
			ptr++;
			break;

		case CODE_CALLBUILTINFUNC:
			DEBUG("print hurr durr\n");
			// TODO: don't assume print
			obj = dynarray_pop(&interp->objstack);
			ok = print_string( interp, (StringObject*)obj );
			OBJECT_DECREF(obj);
			if (!ok)
				goto error;
			ptr++;
			break;

		case CODE_CALLCODEFUNC:
			DEBUG("Calling func\n");
			if (!dynarray_push(interp, &interp->callstack, ptr))
				goto error;
			ptr = &interp->code.ptr[ptr->data.call.jump];
			break;

		case CODE_RETURN:
			DEBUG("Return hurr durr. How much objstack: %zu\n", interp->objstack.len);
			if (interp->callstack.len == 0) {
				DEBUG("return and no more callstack, so we are done\n");
				return true;
			}
			ptr = dynarray_pop(&interp->callstack) + 1;
			break;

		case CODE_SWAP:
			DEBUG("swappinggggg %d %d\n", (int)ptr->data.swap.index1, (int)ptr->data.swap.index2);
			swap(
				&interp->objstack.ptr[interp->objstack.len - ptr->data.swap.index1 - 1],
				&interp->objstack.ptr[interp->objstack.len - ptr->data.swap.index2 - 1]);
			ptr++;
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
