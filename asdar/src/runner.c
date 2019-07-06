#include "runner.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "asdafunc.h"
#include "code.h"
#include "interp.h"
#include "objtyp.h"
#include "partialfunc.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/func.h"
#include "objects/int.h"
#include "objects/scope.h"
#include "objects/string.h"


// change this to choose whether running each op is printed:
#if true
	#include <stdio.h>
	#define DEBUG_PRINTF(...) printf(__VA_ARGS__)
#else
	#define DEBUG_PRINTF(...) ((void)0)
#endif


void runner_init(struct Runner *rnr, Interp *interp, Object *scope, struct Code code)
{
	rnr->interp = interp;
	rnr->scope = scope;
	OBJECT_INCREF(scope);
	rnr->stack = NULL;
	rnr->stacklen = 0;
	rnr->stacksz = 0;
	rnr->code = code;
	rnr->opidx = 0;
	// leave rnr->retval uninitialized for better valgrinding
}

void runner_free(const struct Runner *rnr)
{
	for (size_t i = 0; i < rnr->stacklen; i++)
		OBJECT_DECREF(rnr->stack[i]);
	free(rnr->stack);
	OBJECT_DECREF(rnr->scope);
	// leave rnr->retval untouched, caller of runner_run() should handle its decreffing
}

static bool grow_stack(struct Runner *rnr, size_t minsz)
{
	if (rnr->stacksz >= minsz)
		return true;

	size_t newsz;

	// I haven't tried changing the hard-coded constants to optimize
	if (rnr->stacksz == 0)
		newsz = 3;
	else
		newsz = 2 * rnr->stacksz;

	if (newsz < minsz)
		newsz = minsz;

	Object **ptr = realloc(rnr->stack, sizeof(Object*) * newsz);
	if(!ptr) {
		errobj_set_nomem(rnr->interp);
		return false;
	}
	rnr->stack = ptr;

	rnr->stacksz = newsz;
	return true;
}

static bool push2stack(struct Runner *rnr, Object *obj)
{
	if (!grow_stack(rnr, rnr->stacklen+1))
		return false;
	rnr->stack[rnr->stacklen++] = obj;
	OBJECT_INCREF(obj);
	return true;
}

static Object **get_var_pointer(struct Runner *rnr, const struct CodeOp *op)
{
	Object *scope = scopeobj_getforlevel(rnr->scope, op->data.var.level);
	return scopeobj_getlocalvarsptr(scope) + op->data.var.index;
}

static bool call_function(struct Runner *rnr, bool ret, size_t nargs)
{
	DEBUG_PRINTF("callfunc ret=%s nargs=%zu\n", ret?"true":"false", nargs);
	assert(rnr->stacklen >= nargs + 1);
	rnr->stacklen -= nargs;
	Object **argptr = rnr->stack + rnr->stacklen;
	Object *func = rnr->stack[--rnr->stacklen];

	bool ok;
	Object *res;
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

static bool integer_binary_operation(struct Runner *rnr, enum CodeOpKind bok)
{
	DEBUG_PRINTF("integer binary op\n");
	assert(rnr->stacklen >= 2);
	// y before x because the stack is like this:
	//
	//   |---|---|---|---|---|---|---|---|---|
	//   | stuff we don't care about | x | y |
	Object *y = rnr->stack[--rnr->stacklen];
	Object *x = rnr->stack[--rnr->stacklen];
	Object *res;

	switch(bok) {
		case CODE_INT_ADD: res = intobj_add(rnr->interp, x, y); break;
		case CODE_INT_SUB: res = intobj_sub(rnr->interp, x, y); break;
		case CODE_INT_MUL: res = intobj_mul(rnr->interp, x, y); break;
		default: assert(0);
	}
	OBJECT_DECREF(x);
	OBJECT_DECREF(y);

	if(!res)
		return false;

	rnr->stack[rnr->stacklen++] = res;   // it will fit because x and y came from the stack
	return true;
}


// this function is long, but it feels ok because it divides nicely into max 10-ish line chunks
static enum RunnerResult run_one_op(struct Runner *rnr, const struct CodeOp *op)
{
	enum RunnerResult ret = RUNNER_DIDNTRETURN;

	switch(op->kind) {
	case CODE_CONSTANT:
		DEBUG_PRINTF("constant\n");
		if(!push2stack(rnr, op->data.obj))
			return RUNNER_ERROR;
		break;

	case CODE_SETVAR:
	{
		DEBUG_PRINTF("setvar level=%d index=%d\n",
			(int)op->data.var.level, (int)op->data.var.index);
		assert(rnr->stacklen >= 1);
		Object **ptr = get_var_pointer(rnr, op);
		if(*ptr)
			OBJECT_DECREF(*ptr);

		*ptr = rnr->stack[--rnr->stacklen];
		assert(*ptr);
		break;
	}

	case CODE_GETVAR:
	{
		DEBUG_PRINTF("getvar level=%d index=%d\n",
			(int)op->data.var.level, (int)op->data.var.index);
		Object **ptr = get_var_pointer(rnr, op);
		if(!*ptr) {
			// TODO: include variable name here somehow
			errobj_set(rnr->interp, &errobj_type_variable, "value of a variable hasn't been set");
			return RUNNER_ERROR;
		}

		if(!push2stack(rnr, *ptr))
			return RUNNER_ERROR;
		break;
	}

	case CODE_GETFROMMODULE:
	{
		DEBUG_PRINTF("getfrommodule: pointer = %p, current value = %p\n",
			(void*)op->data.modmemberptr, (void*)*op->data.modmemberptr);
		Object *val = *op->data.modmemberptr;
		if (!val) {
			errobj_set(rnr->interp, &errobj_type_variable, "value of an exported variable hasn't been set");
			return RUNNER_ERROR;
		}

		if (!push2stack(rnr, val))
			return RUNNER_ERROR;
		break;
	}

	case CODE_BOOLNEG:
	{
		DEBUG_PRINTF("boolneg\n");
		assert(rnr->stacklen >= 1);
		Object **ptr = &rnr->stack[rnr->stacklen - 1];
		Object *old = *ptr;
		*ptr = boolobj_c2asda(!boolobj_asda2c(old));
		OBJECT_DECREF(old);
		break;
	}

	case CODE_JUMPIF:
	{
		DEBUG_PRINTF("jumpif\n");
		assert(rnr->stacklen >= 1);
		Object *obj = rnr->stack[--rnr->stacklen];
		bool b = boolobj_asda2c(obj);
		OBJECT_DECREF(obj);

		if(b) {
			DEBUG_PRINTF("  jumping...\n");
			rnr->opidx = op->data.jump_idx;
			goto skip_opidx_plusplus;
		}
		break;
	}

	case CODE_CALLRETFUNC:
		if(!call_function(rnr, true, op->data.callfunc_nargs))
			return RUNNER_ERROR;
		break;
	case CODE_CALLVOIDFUNC:
		if(!call_function(rnr, false, op->data.callfunc_nargs))
			return RUNNER_ERROR;
		break;

	case CODE_GETMETHOD:
	{
		DEBUG_PRINTF("getmethod\n");
		assert(rnr->stacklen >= 1);
		struct CodeLookupMethodData data = op->data.lookupmethod;
		Object **ptr = &rnr->stack[rnr->stacklen - 1];
		Object *parti = partialfunc_create(rnr->interp, data.type->methods[data.index], ptr, 1);
		if(!parti)
			return RUNNER_ERROR;

		OBJECT_DECREF(*ptr);
		*ptr = parti;
		break;
	}

	case CODE_STRJOIN:
	{
		DEBUG_PRINTF("string join of %zu strings\n", (size_t)op->data.strjoin_nstrs);
		assert(rnr->stacklen >= op->data.strjoin_nstrs);
		Object **ptr = rnr->stack + rnr->stacklen - op->data.strjoin_nstrs;
		Object *res = stringobj_join(rnr->interp, ptr, op->data.strjoin_nstrs);
		if(!res)
			return RUNNER_ERROR;

		for (; ptr < rnr->stack + rnr->stacklen; ptr++)
			OBJECT_DECREF(*ptr);

		rnr->stacklen -= op->data.strjoin_nstrs;
		bool ok = push2stack(rnr, res);   // grow the stack if this was a join of 0 strings (result is empty string)
		OBJECT_DECREF(res);

		if (!ok)
			return RUNNER_ERROR;
		break;
	}

	case CODE_POP1:
	{
		DEBUG_PRINTF("pop 1\n");
		assert(rnr->stacklen >= 1);
		Object *obj = rnr->stack[--rnr->stacklen];
		OBJECT_DECREF(obj);
		break;
	}

	case CODE_CREATEFUNC:
	{
		DEBUG_PRINTF("create func\n");
		Object *f = asdafunc_create(rnr->interp, rnr->scope, op->data.createfunc.body, op->data.createfunc.returning);
		bool ok = push2stack(rnr, f);
		OBJECT_DECREF(f);
		if(!ok)
			return RUNNER_ERROR;
		break;
	}

	case CODE_VOIDRETURN:
		DEBUG_PRINTF("void return\n");
		ret = RUNNER_VOIDRETURN;
		break;
	case CODE_VALUERETURN:
		DEBUG_PRINTF("value return\n");
		rnr->retval = rnr->stack[--rnr->stacklen];
		assert(rnr->retval);
		ret = RUNNER_VALUERETURN;
		break;

	case CODE_DIDNTRETURNERROR:
		DEBUG_PRINTF("didn't return error\n");
		// TODO: create a nicer error type for this
		errobj_set(rnr->interp, &errobj_type_value, "function didn't return");
		return RUNNER_ERROR;

	case CODE_INT_ADD:
	case CODE_INT_SUB:
	case CODE_INT_MUL:
		if(!integer_binary_operation(rnr, op->kind))
			return RUNNER_ERROR;
		break;

	case CODE_INT_NEG:
	{
		Object **ptr = &rnr->stack[rnr->stacklen - 1];
		Object *obj = intobj_neg(rnr->interp, *ptr);
		if(!obj)
			return RUNNER_ERROR;
		OBJECT_DECREF(*ptr);
		*ptr = obj;
		break;
	}

	case CODE_INT_EQ:
	{
		Object *x = rnr->stack[--rnr->stacklen];
		Object *y = rnr->stack[--rnr->stacklen];
		rnr->stack[rnr->stacklen++] = boolobj_c2asda(intobj_cmp(x, y) == 0);
		OBJECT_DECREF(x);
		OBJECT_DECREF(y);
	}

	}   // end of switch

	rnr->opidx++;
	// "fall through" to return statement

skip_opidx_plusplus:
	return ret;
}

enum RunnerResult runner_run(struct Runner *rnr)
{
	while (rnr->opidx < rnr->code.nops) {
		enum RunnerResult res = run_one_op(rnr, &rnr->code.ops[rnr->opidx]);
		if(res != RUNNER_DIDNTRETURN)
			return res;
	}

	assert(rnr->opidx == rnr->code.nops);
	return RUNNER_DIDNTRETURN;
}
