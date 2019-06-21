#include "bc.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "objtyp.h"

void bcop_destroy(const struct BcOp *op)
{
	switch(op->kind) {
	case BC_CONSTANT:
		OBJECT_DECREF(op->data.obj);
		break;
	case BC_SETVAR:
	case BC_GETVAR:
	case BC_CALLFUNC:
		break;
	default:
		fprintf(stderr, "op.kind = %d\n", op->kind);
		assert(0);
	}
}

void bcop_destroylist(struct BcOp *op)
{
	struct BcOp *next;
	for (; op; op = next) {
		next = op->next; 	  // may be NULL
		bcop_destroy(op);
		free(op);
	}
}


struct BcOp *bcop_append(struct Interp *interp, struct BcOp *last)
{
	struct BcOp *ptr = malloc(sizeof(*ptr));
	if (!ptr) {
		strcpy(interp->errstr, "not enough memory");
		return NULL;
	}

	if (!last)
		return ptr;
	last->next = ptr;
	return ptr;
}
