// bytecode

#ifndef BC_H
#define BC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "interp.h"

enum BcOpKind {
	BC_CONSTANT,
	BC_SETVAR,
	BC_GETVAR,
	BC_CALLFUNC,
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
	struct Object *obj;
} BcData;

struct BcOp {
	enum BcOpKind kind;
	BcData data;
	uint32_t lineno;
	struct BcOp *next;   // NULL for end of linked list
};

// 'last' should be the last bcop (initially NULL)
// returns the new last bcop or NULL on error
// you need to set all fields of the return value yourself
struct BcOp *bcop_append(struct Interp *interp, struct BcOp *last);

// destroys op, doesn't free it, does nothing with op->next
void bcop_destroy(const struct BcOp *op);

// destroys and frees op, its ->next, its ->next->next etc
void bcop_destroylist(struct BcOp *op);


#endif   // BC_H
