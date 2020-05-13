// structs and stuffs for code that is read from bytecode files and executed

#ifndef CODE_H
#define CODE_H

#include <stddef.h>
#include <stdint.h>
#include "object.h"

enum CodeOpKind {
	CODE_CONSTANT,
	CODE_CALLCODEFUNC,
	CODE_CALLBUILTINFUNC,
	CODE_JUMP,
	CODE_JUMPIF,
	CODE_STRJOIN,
	CODE_THROW,
	CODE_RETURN,

	CODE_DUP,
	CODE_SWAP,
	CODE_POP,
};

struct CodeOp;
typedef union {   // TODO: remove typedef?
	// jumps are relative to start of interp->code
	// objstack indexes are so that 0 is end of objstack
	uint16_t func_nargs;
	size_t jump;
	uint16_t strjoin_nstrs;
	uint16_t objstackincr;  // how much more room in interp->objstack is needed
	uint16_t objstackidx;
	struct CodeCallData { size_t jump; uint16_t nargs; } call;
	const struct BuiltinFunc *builtinfunc;
	struct CodeAttrData { const struct Type *type; uint16_t index; } attr;
	struct CodeSwapData { uint16_t index1, index2; } swap;
	Object *obj;
} CodeData;

struct CodeOp {
	enum CodeOpKind kind;
	CodeData data;
	const char *srcpath;   // relative to interp->basedir
	unsigned long lineno;
};

struct CodeFunctionInfo {
	const struct CodeOp *startptr;
	char *name;
};

// dumps to stdout
void codeop_debug(enum CodeOpKind k);

// called for each op when interpreter quits
void codeop_destroy(struct CodeOp op);


#endif   // CODE_H
