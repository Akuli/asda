#include "runner.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bc.h"
#include "interp.h"
#include "objects/scope.h"
#include "objects/string.h"


void runner_init(struct Runner *rnr, struct Interp *interp, struct Object *scope)
{
	rnr->interp = interp;
	rnr->scope = scope;
	rnr->stack = NULL;
	rnr->stacklen = 0;
	rnr->stacksz = 0;
}

void runner_free(struct Runner *rnr)
{
	for (struct Object **ptr = rnr->stack; ptr < rnr->stack + rnr->stacklen; ptr++)
		OBJECT_DECREF(*ptr);
	free(rnr->stack);
}

static bool grow_stack(struct Runner *rnr, size_t minsz)
{
	if (rnr->stacksz >= minsz)
		return true;

	size_t newsz;

	// I haven't changing the hard-coded constants to optimize
	if (rnr->stacksz == 0)
		newsz = 3;
	else
		newsz = 2 * rnr->stacksz;

	if (newsz < minsz)
		newsz = minsz;

	if (!( rnr->stack = realloc(rnr->stack, sizeof(struct Object*) * newsz) )) {
		interp_errstr_nomem(rnr->interp);
		return false;
	}

	rnr->stacksz = newsz;
	return true;
}

// FIXME: add function objects
static struct Object print = { .interp = NULL, .refcount = 1 };
static struct Object *printptr = &print;

static bool push2stack(struct Runner *rnr, struct Object *obj)
{
	if (!grow_stack(rnr, rnr->stacklen+1))
		return false;
	rnr->stack[rnr->stacklen++] = obj;
	OBJECT_INCREF(obj);
	return true;
}

static struct Object **get_var_pointer(struct Runner *rnr, const struct BcOp *op)
{
	if(op->data.var.level == 0) {
		assert(op->data.var.index == 0);
		return &printptr;
	}
	struct Object *scope = scopeobj_getforlevel(rnr->scope, op->data.var.level);
	return scopeobj_getlocalvarptr(scope, op->data.var.index);
}

bool runner_run(struct Runner *rnr, struct Bc bc)
{
	size_t i = 0;
	while (i < bc.nops) {
//#define DEBUG_PRINTF(...) printf(__VA_ARGS__)
#define DEBUG_PRINTF(...) ((void)0)
		switch(bc.ops[i].kind) {
		case BC_CONSTANT:
			DEBUG_PRINTF("constant\n");
			if(!push2stack(rnr, bc.ops[i].data.obj))
				return false;
			i++;
			break;
		case BC_SETVAR:
		{
			DEBUG_PRINTF("setvar level=%d index=%d\n",
				(int)bc.ops[i].data.var.level, (int)bc.ops[i].data.var.index);
			struct Object **ptr = get_var_pointer(rnr, &bc.ops[i]);
			if(*ptr)
				OBJECT_DECREF(*ptr);
			*ptr = rnr->stack[--rnr->stacklen];
			assert(*ptr);
			i++;
			break;
		}
		case BC_GETVAR:
		{
			DEBUG_PRINTF("getvar level=%d index=%d\n",
				(int)bc.ops[i].data.var.level, (int)bc.ops[i].data.var.index);
			struct Object **ptr = get_var_pointer(rnr, &bc.ops[i]);
			if(!*ptr) {
				interp_errstr_printf(rnr->interp, "value of a variable hasn't been set");
				return false;
			}

			if(!push2stack(rnr, *ptr))
				return false;
			i++;
			break;
		}
		case BC_CALLVOIDFUNC:
		{
			DEBUG_PRINTF("callvoidfunc\n");
			size_t nargs = bc.ops[i].data.callfunc_nargs;
			rnr->stacklen -= nargs;
			struct Object **argptr = rnr->stack + rnr->stacklen;
			struct Object *func = rnr->stack[--rnr->stacklen];
			assert(func == printptr);
			assert(nargs == 1);

			char *str;
			size_t len;
			if(!stringobj_toutf8(*argptr, &str, &len))
				return false;

			for (char *p = str; p < str+len; p++)
				putchar(*p);
			free(str);
			putchar('\n');

			OBJECT_DECREF(func);
			printf("should be 1 i guess: %d\n", func->refcount);
			for(size_t i=0; i < nargs; i++)
				OBJECT_DECREF(argptr[i]);

			i++;
			break;
		}
		default:
			fprintf(stderr, "unknown op kind %d\n", bc.ops[i].kind);
			assert(0);
		}
#undef DEBUG_PRINTF
	}

	return true;
}
