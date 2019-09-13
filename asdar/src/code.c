#include "code.h"
#include <stdio.h>
#include <stdlib.h>
#include "object.h"

void codeop_debug(struct CodeOp op)
{
	switch(op.kind) {
	#define BOILERPLATE(KIND) case KIND: puts(#KIND); break;
		BOILERPLATE(CODE_CONSTANT);
		BOILERPLATE(CODE_SETATTR);
		BOILERPLATE(CODE_GETATTR);
		BOILERPLATE(CODE_SETLOCAL);
		BOILERPLATE(CODE_GETLOCAL);
		BOILERPLATE(CODE_CREATEBOX);
		BOILERPLATE(CODE_SET2BOX);
		BOILERPLATE(CODE_UNBOX);
		BOILERPLATE(CODE_EXPORTOBJECT);
		BOILERPLATE(CODE_GETFROMMODULE);
		BOILERPLATE(CODE_CALLFUNC);
		BOILERPLATE(CODE_CALLCONSTRUCTOR);
		BOILERPLATE(CODE_JUMP);
		BOILERPLATE(CODE_JUMPIF);
		BOILERPLATE(CODE_JUMPIFEQ);
		BOILERPLATE(CODE_STRJOIN);
		BOILERPLATE(CODE_POP1);
		BOILERPLATE(CODE_THROW);
		BOILERPLATE(CODE_CREATEFUNC);
		BOILERPLATE(CODE_CREATEPARTIAL);
		BOILERPLATE(CODE_STORERETVAL);
		BOILERPLATE(CODE_SETMETHODS2CLASS);
		BOILERPLATE(CODE_EH_ADD);
		BOILERPLATE(CODE_EH_RM);
		BOILERPLATE(CODE_FS_OK);
		BOILERPLATE(CODE_FS_ERROR);
		BOILERPLATE(CODE_FS_VALUERETURN);
		BOILERPLATE(CODE_FS_JUMP);
		BOILERPLATE(CODE_FS_APPLY);
		BOILERPLATE(CODE_FS_DISCARD);
		BOILERPLATE(CODE_INT_ADD);
		BOILERPLATE(CODE_INT_SUB);
		BOILERPLATE(CODE_INT_MUL);
		BOILERPLATE(CODE_INT_NEG);
	#undef BOILERPLATE
	}
}

void codeop_destroy(struct CodeOp op)
{
	switch(op.kind) {
	case CODE_CONSTANT:
		OBJECT_DECREF(op.data.obj);
		break;

	case CODE_EH_ADD:
		free(op.data.errhnd.arr);
		break;

	case CODE_CREATEFUNC:
		code_destroy(op.data.createfunc.code);
		break;

	default:
		break;
	}
}

void code_destroy(struct Code code)
{
	for (size_t i = 0; i < code.nops; i++)
		codeop_destroy(code.ops[i]);
	free(code.ops);
}
