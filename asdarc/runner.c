#include "runner.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "bc.h"
#include "interp.h"
#include "objects/bool.h"
#include "objects/func.h"
#include "objects/int.h"
#include "objects/scope.h"
#include "objects/string.h"


// toggle these to choose whether running each op is printed:

//#define DEBUG_PRINTF(...) printf(__VA_ARGS__)
#define DEBUG_PRINTF(...) ((void)0)


void runner_init(struct Runner *rnr, struct Interp *interp, struct Object *scope)
{
	rnr->interp = interp;
	rnr->scope = scope;
	OBJECT_INCREF(scope);
	rnr->stack = NULL;
	rnr->stacklen = 0;
	rnr->stacksz = 0;
}

void runner_free(const struct Runner *rnr)
{
	for (struct Object **ptr = rnr->stack; ptr < rnr->stack + rnr->stacklen; ptr++)
		OBJECT_DECREF(*ptr);
	free(rnr->stack);
	OBJECT_DECREF(rnr->scope);
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
	struct Object *scope = scopeobj_getforlevel(rnr->scope, op->data.var.level);
	return scopeobj_getlocalvarptr(scope, op->data.var.index);
}

static bool call_function(struct Runner *rnr, bool ret, size_t nargs)
{
	DEBUG_PRINTF("callfunc ret=%s nargs=%zu\n", ret?"true":"false", nargs);
	assert(rnr->stacklen >= nargs + 1);
	rnr->stacklen -= nargs;
	struct Object **argptr = rnr->stack + rnr->stacklen;
	struct Object *func = rnr->stack[--rnr->stacklen];

	bool ok;
	struct Object *res;
	if(ret)
		ok = !!( res = funcobj_call_ret(rnr->interp, func, argptr, nargs) );
	else {
		ok = funcobj_call_noret(rnr->interp, func, argptr, nargs);
		res = NULL;
	}

	OBJECT_DECREF(func);
	for(size_t i=0; i < nargs; i++)
		OBJECT_DECREF(argptr[i]);
	if(!ok)
		return false;

	if(res) {
		// it will fit because func (and 0 or more args) came from the stack
		rnr->stack[rnr->stacklen++] = res;
	}
	return true;
}

static bool integer_binary_operation(struct Runner *rnr, enum BcOpKind bok)
{
	DEBUG_PRINTF("integer binary op\n");
	assert(rnr->stacklen >= 2);
	struct Object *x = rnr->stack[--rnr->stacklen];
	struct Object *y = rnr->stack[--rnr->stacklen];
	struct Object *res;

	switch(bok) {
		case BC_INT_ADD: res = intobj_add(rnr->interp, x, y); break;
		case BC_INT_SUB: res = intobj_sub(rnr->interp, x, y); break;
		case BC_INT_MUL: res = intobj_mul(rnr->interp, x, y); break;
		default: assert(0);
	}
	OBJECT_DECREF(x);
	OBJECT_DECREF(y);

	if(!res)
		return false;

	bool ok = push2stack(rnr, res);
	OBJECT_DECREF(res);
	return ok;
}

bool runner_run(struct Runner *rnr, struct Bc bc)
{
	size_t i = 0;
	while (i < bc.nops) {
		switch(bc.ops[i].kind) {
		case BC_CONSTANT:
			DEBUG_PRINTF("constant\n");
			if(!push2stack(rnr, bc.ops[i].data.obj))
				return false;
			break;

		case BC_SETVAR:
		{
			DEBUG_PRINTF("setvar level=%d index=%d\n",
				(int)bc.ops[i].data.var.level, (int)bc.ops[i].data.var.index);
			assert(rnr->stacklen >= 1);
			struct Object **ptr = get_var_pointer(rnr, &bc.ops[i]);
			if(*ptr)
				OBJECT_DECREF(*ptr);
			*ptr = rnr->stack[--rnr->stacklen];
			assert(*ptr);
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
			break;
		}

		case BC_BOOLNEG:
		{
			DEBUG_PRINTF("boolneg\n");
			assert(rnr->stacklen >= 1);
			struct Object **ptr = &rnr->stack[rnr->stacklen - 1];
			struct Object *old = *ptr;
			*ptr = boolobj_c2asda(!boolobj_asda2c(old));
			OBJECT_DECREF(old);
			break;
		}
		case BC_JUMPIF:
		{
			DEBUG_PRINTF("jumpif\n");
			assert(rnr->stacklen >= 1);
			struct Object *ocond = rnr->stack[--rnr->stacklen];
			bool bcond = boolobj_asda2c(ocond);
			OBJECT_DECREF(ocond);
			if(bcond) {
				DEBUG_PRINTF("  jumping...\n");
				i = bc.ops[i].data.jump_idx;
				goto skip_iplusplus;
			}
			break;
		}

		case BC_CALLRETFUNC:
			if(!call_function(rnr, true, bc.ops[i].data.callfunc_nargs))
				return false;
			break;
		case BC_CALLVOIDFUNC:
			if(!call_function(rnr, false, bc.ops[i].data.callfunc_nargs))
				return false;
			break;

		case BC_GETMETHOD:
		{
			DEBUG_PRINTF("getmethod\n");
			assert(rnr->stacklen >= 1);
			struct BcLookupMethodData data = bc.ops[i].data.lookupmethod;
			struct Object **ptr = &rnr->stack[rnr->stacklen - 1];
			struct Object *parti = funcobj_new_partial(rnr->interp, data.type->methods[data.index], ptr, 1);
			if(!parti)
				return false;
			OBJECT_DECREF(*ptr);
			*ptr = parti;
			break;
		}

		case BC_STRJOIN:
		{
			DEBUG_PRINTF("string join of %zu strings\n", (size_t)bc.ops[i].data.strjoin_nstrs);
			assert(rnr->stacklen >= bc.ops[i].data.strjoin_nstrs);
			struct Object **ptr = rnr->stack + rnr->stacklen - bc.ops[i].data.strjoin_nstrs;
			struct Object *res = stringobj_join(rnr->interp, ptr, bc.ops[i].data.strjoin_nstrs);
			if(!res)
				return false;

			for (; ptr < rnr->stack + rnr->stacklen; ptr++)
				OBJECT_DECREF(*ptr);

			rnr->stacklen -= bc.ops[i].data.strjoin_nstrs;
			rnr->stack[rnr->stacklen++] = res;
			break;
		}

		case BC_INT_ADD:
		case BC_INT_SUB:
		case BC_INT_MUL:
			if(!integer_binary_operation(rnr, bc.ops[i].kind))
				return false;
			break;

		case BC_INT_NEG:
		{
			struct Object **ptr = &rnr->stack[rnr->stacklen - 1];
			struct Object *obj = intobj_neg(rnr->interp, *ptr);
			if(!obj)
				return false;
			OBJECT_DECREF(*ptr);
			*ptr = obj;
			break;
		}

		}   // end of switch

		i++;
skip_iplusplus:
		(void)0;   // this does nothing, it's needed because c syntax is awesome
	}
	assert(i == bc.nops);

	return true;
}
