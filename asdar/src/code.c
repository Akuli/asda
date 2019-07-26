#include "code.h"
#include <stdlib.h>
#include "object.h"

void codeop_destroy(const struct CodeOp *op)
{
	switch(op->kind) {
	case CODE_CONSTANT:
		OBJECT_DECREF(op->data.obj);
		break;

	case CODE_EH_ADD:
		free(op->data.errhnd.arr);
		break;

	case CODE_CREATEFUNC:
		code_destroy(&op->data.createfunc.code);
		break;

	default:
		break;
	}
}

void code_destroy(const struct Code *code)
{
	for (size_t i = 0; i < code->nops; i++)
		codeop_destroy(&code->ops[i]);
	free(code->ops);
}
