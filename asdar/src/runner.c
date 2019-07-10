#include "runner.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include "asdafunc.h"
#include "dynarray.h"
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

/*
#include <stdio.h>
#define DEBUG_PRINTF(...) printf(__VA_ARGS__)
*/
#define DEBUG_PRINTF(...) ((void)0)

void runner_init(struct Runner *rnr, Interp *interp, Object *scope, struct Code code)
{
	rnr->interp = interp;
	rnr->scope = scope;
	OBJECT_INCREF(scope);
	dynarray_init(&rnr->stack);
	rnr->code = code;
	rnr->opidx = 0;
	// leave rnr->retval uninitialized for better valgrinding
}

void runner_free(const struct Runner *rnr)
{
	for (size_t i = 0; i < rnr->stack.len; i++)
		OBJECT_DECREF(rnr->stack.ptr[i]);
	free(rnr->stack.ptr);
	OBJECT_DECREF(rnr->scope);
	// leave rnr->retval untouched, caller of runner_run() should handle its decreffing
}

static bool push2stack(struct Runner *rnr, Object *obj)
{
	if (!dynarray_push(rnr->interp, &rnr->stack, obj))
		return false;
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
	assert(rnr->stack.len >= nargs + 1);
	rnr->stack.len -= nargs;
	Object **argptr = rnr->stack.ptr + rnr->stack.len;
	Object *func = dynarray_pop(&rnr->stack);

	Object *result;
	bool ok = funcobj_call(rnr->interp, func, argptr, nargs, &result);

	OBJECT_DECREF(func);
	for(size_t i=0; i < nargs; i++) OBJECT_DECREF(argptr[i]);

	if(!ok) return false;

	if(result)
		dynarray_push_itwillfit(&rnr->stack, result);
	return true;
}

static bool integer_binary_operation(struct Runner *rnr, enum CodeOpKind bok)
{
	DEBUG_PRINTF("integer binary op\n");
	assert(rnr->stack.len >= 2);
	// y before x because the stack is like this:
	//
	//   |---|---|---|---|---|---|---|---|---|
	//   | stuff we don't care about | x | y |
	Object *y = dynarray_pop(&rnr->stack);
	Object *x = dynarray_pop(&rnr->stack);
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
	dynarray_push_itwillfit(&rnr->stack, res);
	return true;
}


// this function is long, but it feels ok because it divides nicely into max 10-ish line chunks
static enum RunnerResult run_one_op(struct Runner *rnr, const struct CodeOp *op)
{
	DEBUG_PRINTF("%d: ", op->lineno);

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
		assert(rnr->stack.len >= 1);
		Object **ptr = get_var_pointer(rnr, op);
		if(*ptr)
			OBJECT_DECREF(*ptr);

		*ptr = dynarray_pop(&rnr->stack);
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
		assert(rnr->stack.len >= 1);
		Object **ptr = &rnr->stack.ptr[rnr->stack.len - 1];
		Object *old = *ptr;
		*ptr = boolobj_neg(old);
		OBJECT_DECREF(old);
		break;
	}

	case CODE_JUMPIF:
	{
		DEBUG_PRINTF("jumpif\n");
		assert(rnr->stack.len >= 1);
		Object *obj = dynarray_pop(&rnr->stack);
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
		assert(rnr->stack.len >= 1);
		struct CodeLookupMethodData data = op->data.lookupmethod;
		Object **ptr = &rnr->stack.ptr[rnr->stack.len - 1];
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
		assert(rnr->stack.len >= op->data.strjoin_nstrs);
		Object **ptr = rnr->stack.ptr + rnr->stack.len - op->data.strjoin_nstrs;
		Object *res = stringobj_join(rnr->interp, ptr, op->data.strjoin_nstrs);
		if(!res)
			return RUNNER_ERROR;

		for (; ptr < rnr->stack.ptr + rnr->stack.len; ptr++)
			OBJECT_DECREF(*ptr);

		rnr->stack.len -= op->data.strjoin_nstrs;
		bool ok = push2stack(rnr, res);   // grows the stack if this was a join of 0 strings (result is empty string)
		OBJECT_DECREF(res);

		if (!ok)
			return RUNNER_ERROR;
		break;
	}

	case CODE_POP1:
	{
		DEBUG_PRINTF("pop 1\n");
		assert(rnr->stack.len >= 1);
		Object *obj = dynarray_pop(&rnr->stack);
		OBJECT_DECREF(obj);
		break;
	}

	case CODE_CREATEFUNC:
	{
		DEBUG_PRINTF("create func\n");
		Object *f = asdafunc_create(rnr->interp, rnr->scope, op->data.createfunc_code);
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
		rnr->retval = dynarray_pop(&rnr->stack);
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
		Object **ptr = &rnr->stack.ptr[rnr->stack.len - 1];
		Object *obj = intobj_neg(rnr->interp, *ptr);
		if(!obj)
			return RUNNER_ERROR;
		OBJECT_DECREF(*ptr);
		*ptr = obj;
		break;
	}

	case CODE_INT_EQ:
	{
		Object *x = dynarray_pop(&rnr->stack);
		Object *y = dynarray_pop(&rnr->stack);
		Object *res = boolobj_c2asda(intobj_cmp(x, y) == 0);
		dynarray_push(rnr->interp, &rnr->stack, res);
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
