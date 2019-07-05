// structs and stuffs for code that is read from bytecode files and executed

#ifndef CODE_H
#define CODE_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "objtyp.h"

enum CodeOpKind {
	CODE_CONSTANT,
	CODE_SETVAR,
	CODE_GETVAR,
	CODE_GETMETHOD,
	CODE_GETFROMMODULE,
	CODE_CALLVOIDFUNC,
	CODE_CALLRETFUNC,
	CODE_BOOLNEG,
	CODE_JUMPIF,
	CODE_STRJOIN,
	CODE_POP1,

	CODE_CREATEFUNC,
	CODE_VOIDRETURN,
	CODE_VALUERETURN,
	CODE_DIDNTRETURNERROR,

	CODE_INT_ADD,   // x+y
	CODE_INT_SUB,   // x-y
	CODE_INT_NEG,   // -x
	CODE_INT_MUL,   // x*y
	CODE_INT_EQ,    // x == y
};

struct CodeOp;
struct Code {
	struct CodeOp *ops;
	size_t nops;
	uint16_t nlocalvars;
};

struct CodeVarData { uint8_t level; uint16_t index; };
struct CodeLookupMethodData { const struct Type *type; uint16_t index; };
struct CodeCreateFuncData { bool returning; struct Code body; };

typedef union {
	struct CodeVarData var;
	uint8_t callfunc_nargs;
	uint16_t jump_idx;
	uint16_t strjoin_nstrs;
	struct CodeLookupMethodData lookupmethod;
	struct CodeCreateFuncData createfunc;
	Object *obj;
	Object **modmemberptr;
} CodeData;

struct CodeOp {
	enum CodeOpKind kind;
	CodeData data;
	uint32_t lineno;
};

// destroys op, doesn't free it
void codeop_destroy(const struct CodeOp *op);

// doesn't free code itself, but frees all contents nicely
void code_destroy(const struct Code *code);


#endif   // CODE_H
