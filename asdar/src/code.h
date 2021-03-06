// structs and stuffs for code that is read from bytecode files and executed

#ifndef CODE_H
#define CODE_H

#include <stddef.h>
#include <stdint.h>
#include "object.h"

enum CodeOpKind {
	CODE_CONSTANT,
	CODE_SETATTR,
	CODE_GETATTR,
	CODE_SETLOCAL,
	CODE_GETLOCAL,
	CODE_CREATEBOX,
	CODE_SET2BOX,
	CODE_UNBOX,
	CODE_EXPORTOBJECT,
	CODE_GETFROMMODULE,
	CODE_CALLFUNC,
	CODE_CALLCONSTRUCTOR,
	CODE_JUMP,
	CODE_JUMPIF,
	CODE_JUMPIFEQ_INT,
	CODE_JUMPIFEQ_STR,
	CODE_STRJOIN,
	CODE_THROW,
	CODE_SETMETHODS2CLASS,
	CODE_POP1,

	CODE_CREATEFUNC,
	CODE_CREATEPARTIAL,
	CODE_STORERETVAL,

	// EH = Error Handler, see finally.md
	CODE_EH_ADD,
	CODE_EH_RM,

	// FS = Finally State, see finally.md
	CODE_FS_OK,
	CODE_FS_ERROR,
	CODE_FS_VALUERETURN,
	CODE_FS_JUMP,

	CODE_FS_APPLY,
	CODE_FS_DISCARD,

	CODE_INT_ADD,   // x+y
	CODE_INT_SUB,   // x-y
	CODE_INT_MUL,   // x*y
	CODE_INT_NEG,   // -x
};

struct CodeOp;
struct Code {
	const char *srcpath;   // relative to interp->basedir, same for every code of a module
	struct CodeOp *ops;
	size_t nops;
	uint16_t nlocalvars, maxstacksz;
};

struct CodeErrHndItem { const struct Type *errtype; uint16_t errvar; uint16_t jmpidx; };
struct CodeErrHnd { struct CodeErrHndItem *arr; size_t len; };

struct CodeConstructorData { const struct Type *type; size_t nargs; };
struct CodeCreateFuncData { const struct TypeFunc *type; struct Code code; };
struct CodeAttrData { const struct Type *type; uint16_t index; };
struct CodeSetMethodsData { const struct TypeAsdaClass *type; uint16_t nmethods; };

typedef union {
	uint16_t func_nargs;
	uint16_t jump_idx;
	uint16_t strjoin_nstrs;
	uint16_t localvaridx;
	struct CodeAttrData attr;
	struct CodeErrHnd errhnd;
	struct CodeCreateFuncData createfunc;
	struct CodeConstructorData constructor;
	struct CodeSetMethodsData setmethods;
	Object *obj;
	Object **modmemberptr;
} CodeData;

struct CodeOp {
	enum CodeOpKind kind;
	CodeData data;
	unsigned long lineno;
};

// dumps to stdout
void codeop_debug(struct CodeOp op);

// destroys op, doesn't free it
void codeop_destroy(struct CodeOp op);

// frees the contents of the code struct nicely
void code_destroy(struct Code code);


#endif   // CODE_H
