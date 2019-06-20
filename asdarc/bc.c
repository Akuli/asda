#include "bc.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>

static void destroy_op(struct BcOp op)
{
	switch(op.kind) {
	default:
		fprintf(stderr, "op.kind = %c\n", (char)op.kind);
		assert(0);
	}
}

void bc_destroyops(struct BcOp *op)
{
	struct BcOp *next;
	for (; op; op = next) {
		next = op->next; 	  // may be NULL
		destroy_op(*op);
		free(op);
	}
}
