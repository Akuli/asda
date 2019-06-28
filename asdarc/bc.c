#include "bc.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "objtyp.h"

void bcop_destroy(const struct BcOp *op)
{
	switch(op->kind) {
	case BC_CONSTANT:
		OBJECT_DECREF(op->data.obj);
		break;
	case BC_SETVAR:
	case BC_GETVAR:
	case BC_GETMETHOD:
	case BC_CALLVOIDFUNC:
	case BC_CALLRETFUNC:
	case BC_BOOLNEG:
	case BC_JUMPIF:
		break;
	}
}

void bc_destroy(const struct Bc *bc)
{
	for (struct BcOp *ptr = bc->ops; ptr < bc->ops + bc->nops; ptr++)
		bcop_destroy(ptr);
	free(bc->ops);
}
