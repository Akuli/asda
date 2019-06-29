#include "bc.h"
#include <stdlib.h>
#include "objtyp.h"

void bcop_destroy(const struct BcOp *op)
{
	switch(op->kind) {
	case BC_CONSTANT:
		OBJECT_DECREF(op->data.obj);
		break;

	case BC_CREATEFUNC:
		bc_destroy(&op->data.createfunc.body);
		break;

	case BC_SETVAR:
	case BC_GETVAR:
	case BC_GETMETHOD:
	case BC_CALLVOIDFUNC:
	case BC_CALLRETFUNC:
	case BC_BOOLNEG:
	case BC_JUMPIF:
	case BC_STRJOIN:
	case BC_POP1:
	case BC_VOIDRETURN:
	case BC_VALUERETURN:
	case BC_DIDNTRETURNERROR:
	case BC_INT_ADD:
	case BC_INT_SUB:
	case BC_INT_NEG:
	case BC_INT_MUL:
		break;
	}
}

void bc_destroy(const struct Bc *bc)
{
	for (size_t i = 0; i < bc->nops; i++)
		bcop_destroy(&bc->ops[i]);
	free(bc->ops);
}
