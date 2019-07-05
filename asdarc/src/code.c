#include "code.h"
#include <stdlib.h>
#include "objtyp.h"

void codeop_destroy(const struct CodeOp *op)
{
	switch(op->kind) {
	case CODE_CONSTANT:
		OBJECT_DECREF(op->data.obj);
		break;

	case CODE_CREATEFUNC:
		code_destroy(&op->data.createfunc.body);
		break;

	case CODE_SETVAR:
	case CODE_GETVAR:
	case CODE_GETMETHOD:
	case CODE_GETFROMPTR:
	case CODE_CALLVOIDFUNC:
	case CODE_CALLRETFUNC:
	case CODE_BOOLNEG:
	case CODE_JUMPIF:
	case CODE_STRJOIN:
	case CODE_POP1:
	case CODE_VOIDRETURN:
	case CODE_VALUERETURN:
	case CODE_DIDNTRETURNERROR:
	case CODE_INT_ADD:
	case CODE_INT_SUB:
	case CODE_INT_NEG:
	case CODE_INT_MUL:
		break;
	}
}

void code_destroy(const struct Code *code)
{
	for (size_t i = 0; i < code->nops; i++)
		codeop_destroy(&code->ops[i]);
	free(code->ops);
}
