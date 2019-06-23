// bytecode

#ifndef BC_H
#define BC_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>

enum BcOpKind {
	BC_CONSTANT,
	BC_SETVAR,
	BC_GETVAR,
	BC_CALLVOIDFUNC,
	BC_CALLRETFUNC,
	BC_BOOLNEG,
	BC_JUMPIF,
};

struct BcOp;
struct Bc {
	struct BcOp *ops;
	size_t nops;
	uint16_t nlocalvars;
};

struct BcVarData { uint8_t level; uint16_t index; };
struct BcLookupAttribData { struct Type *type; uint16_t index; };
struct BcCreateFuncData { bool returning; struct Bc body; };

typedef union {
	struct BcVarData var;
	uint8_t callfunc_nargs;
	uint16_t jump_idx;
	struct BcLookupAttribData lookupattrib;
	struct BcCreateFuncData createfunc;
	struct Object *obj;
} BcData;

struct BcOp {
	enum BcOpKind kind;
	BcData data;
	uint32_t lineno;
};

// destroys op, doesn't free it
void bcop_destroy(const struct BcOp *op);

// doesn't free bc itself, but frees all contents nicely
void bc_destroy(const struct Bc *bc);


#endif   // BC_H
