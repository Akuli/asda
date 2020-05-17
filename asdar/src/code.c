#include "code.h"
#include <stdio.h>
#include "cfunc.h"
#include "object.h"

void codeop_debug(struct CodeOp co)
{
	switch(co.kind) {
	case CODE_CONSTANT:
		printf("CODE_CONSTANT(%p)\n", (void*)co.data.obj);
		break;

	case CODE_CALLCODEFUNC:
		printf("CODE_CALLCODEFUNC(jump=%zu nargs=%zu)\n",
			co.data.call.jump, (size_t)co.data.call.nargs);
		break;

	case CODE_CALLBUILTINFUNC:
		printf("CODE_CALLBUILTINFUNC(%s)\n", co.data.cfunc->name);
		break;

	case CODE_JUMP:
		printf("CODE_JUMP(%zu)\n", co.data.jump);
		break;

	case CODE_JUMPIF:
		printf("CODE_JUMPIF(%zu)\n", co.data.jump);
		break;

	case CODE_STRJOIN:
		printf("CODE_STRJOIN(%zu)\n", (size_t)co.data.strjoin_nstrs);
		break;

	case CODE_DUP:
		printf("CODE_DUP(%zu)\n", (size_t)co.data.objstackidx);
		break;

	case CODE_SWAP:
		printf("CODE_SWAP(%zu, %zu)\n", (size_t)co.data.swap.index1, (size_t)co.data.swap.index2);
		break;

	#define BOILERPLATE(KIND) case KIND: puts(#KIND); break;
		BOILERPLATE(CODE_THROW)
		BOILERPLATE(CODE_RETURN)
		BOILERPLATE(CODE_POP)
	#undef BOILERPLATE
	}
}

void codeop_destroy(struct CodeOp op)
{
	if (op.kind == CODE_CONSTANT)
		OBJECT_DECREF(op.data.obj);
}
