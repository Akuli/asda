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

void runner_init(struct Runner *rnr, Interp *interp, ScopeObject *scope, struct Code code)
{
	rnr->interp = interp;
	rnr->scope = scope;
	OBJECT_INCREF(scope);
	dynarray_init(&rnr->stack);
	dynarray_init(&rnr->ehstack);
	dynarray_init(&rnr->fsstack);
	rnr->code = code;
	rnr->opidx = 0;
	// leave rnr->retval uninitialized for better valgrinding
}

static void destroy_finally_state(struct RunnerFinallyState fs)
{
	if (fs.kind == CODE_FS_ERROR || fs.kind == CODE_FS_VALUERETURN)
		OBJECT_DECREF(fs.val.obj);
}

void runner_free(const struct Runner *rnr)
{
	assert(rnr->stack.len == 0);
	assert(rnr->ehstack.len == 0);
	assert(rnr->fsstack.len == 0);

	free(rnr->stack.ptr);
	free(rnr->ehstack.ptr);
	free(rnr->fsstack.ptr);

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
	ScopeObject *scope = scopeobj_getforlevel(rnr->scope, op->data.var.level);
	return scope->locals + op->data.var.index;
}

static bool call_function(struct Runner *rnr, bool ret, size_t nargs)
{
	DEBUG_PRINTF("callfunc ret=%s nargs=%zu\n", ret?"true":"false", nargs);
	assert(rnr->stack.len >= nargs + 1);
	rnr->stack.len -= nargs;
	Object **argptr = rnr->stack.ptr + rnr->stack.len;
	FuncObject *func = (FuncObject *)dynarray_pop(&rnr->stack);

	Object *result;
	bool ok = funcobj_call(rnr->interp, func, argptr, nargs, &result);

	OBJECT_DECREF(func);
	for(size_t i=0; i < nargs; i++) OBJECT_DECREF(argptr[i]);

	if (ok && result)
		dynarray_push_itwillfit(&rnr->stack, result);
	return ok;
}

static bool integer_binary_operation(struct Runner *rnr, enum CodeOpKind bok)
{
	DEBUG_PRINTF("integer binary op\n");
	assert(rnr->stack.len >= 2);
	// y before x because the stack is like this:
	//
	//   |---|---|---|---|---|---|---|---|---|
	//   | stuff we don't care about | x | y |
	IntObject *y = (IntObject *)dynarray_pop(&rnr->stack);
	IntObject *x = (IntObject *)dynarray_pop(&rnr->stack);
	IntObject *res;

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
	dynarray_push_itwillfit(&rnr->stack, (Object*)res);
	return true;
}

static enum RunnerResult apply_finally_state(struct Runner *rnr, struct RunnerFinallyState fs)
{
	switch (fs.kind) {
		case CODE_FS_OK:
			return RUNNER_DIDNTRETURN;
		case CODE_FS_ERROR:
			errobj_set_obj(rnr->interp, (ErrObject *)fs.val.obj);
			return RUNNER_ERROR;
		case CODE_FS_VOIDRETURN:
			return RUNNER_VOIDRETURN;
		case CODE_FS_VALUERETURN:
			rnr->retval = fs.val.obj;
			OBJECT_INCREF(rnr->retval);
			return RUNNER_DIDNTRETURN;
		case CODE_FS_JUMP:
			rnr->opidx = fs.val.jumpidx;
			return RUNNER_DIDNTRETURN;
		default:
			assert(0);
			break;
	}
}


// this function is long, but it feels ok because it divides nicely into max 10-ish line chunks
static enum RunnerResult run_one_op(struct Runner *rnr, const struct CodeOp *op)
{
	DEBUG_PRINTF("%d: ", op->lineno);

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
		BoolObject **ptr = (BoolObject **)&rnr->stack.ptr[rnr->stack.len - 1];
		BoolObject *old = *ptr;
		*ptr = boolobj_c2asda(!boolobj_asda2c(old));
		OBJECT_DECREF(old);
		break;
	}

	case CODE_JUMP:
		rnr->opidx = op->data.jump_idx;
		goto skip_opidx_plusplus;

	case CODE_JUMPIF:
	{
		DEBUG_PRINTF("jumpif\n");
		assert(rnr->stack.len >= 1);
		BoolObject *obj = (BoolObject *)dynarray_pop(&rnr->stack);
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
		FuncObject *parti = partialfunc_create(rnr->interp, data.type->methods[data.index], ptr, 1);
		if(!parti)
			return RUNNER_ERROR;

		OBJECT_DECREF(*ptr);
		*ptr = (Object *)parti;
		break;
	}

	// TODO: refactor this into a separate function, is 2 long
	case CODE_STRJOIN:
	{
		DEBUG_PRINTF("string join of %zu strings\n", (size_t)op->data.strjoin_nstrs);
		assert(rnr->stack.len >= op->data.strjoin_nstrs);
		Object **ptr = rnr->stack.ptr + rnr->stack.len - op->data.strjoin_nstrs;
		StringObject *res = stringobj_join(rnr->interp, (StringObject **)ptr, op->data.strjoin_nstrs);
		if(!res)
			return RUNNER_ERROR;

		for (; ptr < rnr->stack.ptr + rnr->stack.len; ptr++)
			OBJECT_DECREF(*ptr);

		rnr->stack.len -= op->data.strjoin_nstrs;
		bool ok = push2stack(rnr, (Object *)res);   // grows the stack if this was a join of 0 strings (result is empty string)
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
		FuncObject *f = asdafunc_create(rnr->interp, rnr->scope, op->data.createfunc_code);
		bool ok = push2stack(rnr, (Object *)f);
		OBJECT_DECREF(f);
		if(!ok)
			return RUNNER_ERROR;
		break;
	}

	case CODE_VOIDRETURN:
		DEBUG_PRINTF("void return\n");
		return RUNNER_VOIDRETURN;
	case CODE_VALUERETURN:
		DEBUG_PRINTF("value return\n");
		rnr->retval = dynarray_pop(&rnr->stack);
		assert(rnr->retval);
		return RUNNER_VALUERETURN;

	case CODE_DIDNTRETURNERROR:
		DEBUG_PRINTF("didn't return error\n");
		// TODO: create a nicer error type for this
		errobj_set(rnr->interp, &errobj_type_value, "function didn't return");
		return RUNNER_ERROR;

	case CODE_THROW:
	{
		Object *e = dynarray_pop(&rnr->stack);
		errobj_set_obj(rnr->interp, (ErrObject *)e);
		OBJECT_DECREF(e);
		return RUNNER_ERROR;
	}

	case CODE_FS_OK:
	case CODE_FS_ERROR:
	case CODE_FS_VOIDRETURN:
	case CODE_FS_VALUERETURN:
	case CODE_FS_JUMP:
	{
		struct RunnerFinallyState fs;
		fs.kind = op->kind;
		if (op->kind == CODE_FS_ERROR || op->kind == CODE_FS_VALUERETURN)
			fs.val.obj = dynarray_pop(&rnr->stack);
		if (op->kind == CODE_FS_VALUERETURN)
			fs.val.jumpidx = op->data.jump_idx;

		if (!dynarray_push(rnr->interp, &rnr->fsstack, fs)) {
			destroy_finally_state(fs);
			return RUNNER_ERROR;
		}
		break;
	}

	case CODE_FS_APPLY:
	{
		struct RunnerFinallyState fs = dynarray_pop(&rnr->fsstack);
		enum RunnerResult r = apply_finally_state(rnr, fs);
		destroy_finally_state(fs);
		if (r != RUNNER_DIDNTRETURN)
			return r;
		break;
	}

	case CODE_FS_DISCARD:
	{
		assert(rnr->fsstack.len);
		struct RunnerFinallyState fs = dynarray_pop(&rnr->fsstack);
		destroy_finally_state(fs);
		break;
	}

	case CODE_ERRHND_ADD:
		if (!dynarray_push(rnr->interp, &rnr->ehstack, op->data.errhnd))
			return RUNNER_ERROR;
		break;
	case CODE_ERRHND_RM:
		(void) dynarray_pop(&rnr->ehstack);
		break;

	case CODE_INT_ADD:
	case CODE_INT_SUB:
	case CODE_INT_MUL:
		if(!integer_binary_operation(rnr, op->kind))
			return RUNNER_ERROR;
		break;

	case CODE_INT_NEG:
	{
		IntObject **ptr = (IntObject **)&rnr->stack.ptr[rnr->stack.len - 1];
		IntObject *obj = intobj_neg(rnr->interp, *ptr);
		if(!obj)
			return RUNNER_ERROR;
		OBJECT_DECREF(*ptr);
		*ptr = obj;
		break;
	}

	case CODE_INT_EQ:
	{
		IntObject *x = (IntObject *)dynarray_pop(&rnr->stack);
		IntObject *y = (IntObject *)dynarray_pop(&rnr->stack);
		BoolObject *res = boolobj_c2asda(intobj_cmp(x, y) == 0);
		dynarray_push_itwillfit(&rnr->stack, (Object*)res);
		OBJECT_DECREF(x);
		OBJECT_DECREF(y);
		break;
	}

	}   // end of switch

	rnr->opidx++;
	// "fall through" to return statement

skip_opidx_plusplus:
	return RUNNER_DIDNTRETURN;
}

static void run_error_handler(struct Runner *rnr)
{
	struct CodeErrHndData eh = dynarray_pop(&rnr->ehstack);
	rnr->opidx = eh.jmpidx;

	assert(rnr->interp->err);
	if (rnr->scope->locals[eh.errvar])
		OBJECT_DECREF(rnr->scope->locals[eh.errvar]);
	rnr->scope->locals[eh.errvar] = (Object *)rnr->interp->err;
	rnr->interp->err = NULL;
}

static void clear_stack(struct Runner *rnr)
{
	for (size_t i = 0; i < rnr->stack.len; i++)
		OBJECT_DECREF(rnr->stack.ptr[i]);
	rnr->stack.len = 0;
}

enum RunnerResult runner_run(struct Runner *rnr)
{
	while (rnr->opidx < rnr->code.nops) {
		enum RunnerResult res = run_one_op(rnr, &rnr->code.ops[rnr->opidx]);
		if (res == RUNNER_ERROR) {
			clear_stack(rnr);
			if (rnr->ehstack.len) {
				run_error_handler(rnr);
				continue;
			}
		}

		if(res != RUNNER_DIDNTRETURN)
			return res;
	}

	assert(rnr->opidx == rnr->code.nops);
	return RUNNER_DIDNTRETURN;
}
