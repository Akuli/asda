// structs and stuffs for code that is read from bytecode files and executed

#ifndef CODE_H
#define CODE_H

#include <stddef.h>
#include <stdint.h>
#include "object.h"

enum CodeOpKind {
	CODE_CONSTANT,
	CODE_SETVAR,
	CODE_GETVAR,
	CODE_GETMETHOD,
	CODE_GETFROMMODULE,
	CODE_CALLFUNC,
	CODE_CALLCONSTRUCTOR,
	CODE_BOOLNEG,
	CODE_JUMP,
	CODE_JUMPIF,
	CODE_STRJOIN,
	CODE_POP1,
	CODE_THROW,

	CODE_CREATEFUNC,
	CODE_VOIDRETURN,
	CODE_VALUERETURN,
	CODE_DIDNTRETURNERROR,

	// EH = Error Handler, see finally.md
	CODE_EH_ADD,
	CODE_EH_RM,

	// FS = Finally State, see finally.md
	CODE_FS_OK,
	CODE_FS_ERROR,
	CODE_FS_VOIDRETURN,
	CODE_FS_VALUERETURN,
	CODE_FS_JUMP,

	CODE_FS_APPLY,
	CODE_FS_DISCARD,

	CODE_INT_ADD,   // x+y
	CODE_INT_SUB,   // x-y
	CODE_INT_MUL,   // x*y
	CODE_INT_NEG,   // -x
	CODE_INT_EQ,    // x == y
};

struct CodeOp;
struct Code {
	const char *srcpath;   // relative to interp->basedir, same for every code of a module
	struct CodeOp *ops;
	size_t nops;
	uint16_t nlocalvars;
};

struct CodeErrHndItem { const struct Type *errtype; uint16_t errvar; uint16_t jmpidx; };
struct CodeErrHnd { struct CodeErrHndItem *arr; size_t len; };

struct CodeConstructorData { const struct Type *type; size_t nargs; };
struct CodeCreateFuncData { const struct TypeFunc *type; struct Code code; };
struct CodeLookupMethodData { const struct Type *type; uint16_t index; };
struct CodeVarData { uint8_t level; uint16_t index; };

typedef union {
	struct CodeVarData var;
	uint8_t callfunc_nargs;
	uint16_t jump_idx;
	uint16_t strjoin_nstrs;
	struct CodeLookupMethodData lookupmethod;
	struct CodeErrHnd errhnd;
	struct CodeCreateFuncData createfunc;
	struct CodeConstructorData constructor;
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
