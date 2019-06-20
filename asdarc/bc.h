// bytecode

#ifndef BC_H
#define BC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum BcOpKind {
	BC_OP_CONSTANT,
};

struct BcOp;
struct Bc {
	struct BcOp *firstop;   // NULL if no ops
	uint16_t nlocalvars;
};

struct BcVarData { uint8_t level; uint16_t index; };
struct BcCallFuncData { bool returning; uint8_t nargs; };
struct BcLookupAttribData { struct Type *type; uint16_t index; };
struct BcCreateFuncData { bool returning; struct Bc body; };

typedef union {
	struct BcVarData var;
	struct BcCallFuncData callfunc;
	struct BcLookupAttribData lookupattrib;
	struct BcCreateFuncData createfunc;
} BcData;

struct BcOp {
	enum BcOpKind kind;
	BcData data;
	uint32_t lineno;
	struct BcOp *next;   // NULL for end of linked list
};

// frees op, its ->next, its ->next->next etc
void bc_destroyops(struct BcOp *op);


#endif   // BC_H
