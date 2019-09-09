#include "runner.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "asdafunc.h"
#include "code.h"
#include "dynarray.h"
#include "interp.h"
#include "object.h"
#include "partialfunc.h"
#include "type.h"
#include "objects/asdainst.h"
#include "objects/bool.h"
#include "objects/box.h"
#include "objects/err.h"
#include "objects/func.h"
#include "objects/int.h"
#include "objects/string.h"

/*
#include <stdio.h>
#define DEBUG_PRINTF(...) printf(__VA_ARGS__)
*/
#define DEBUG_PRINTF(...) ((void)0)

// see finally.md
struct RunnerFinallyState {
	enum CodeOpKind kind;   // one of CODE_FS_* things, but not CODE_FS_APPLY or CODE_FS_DISCARD
	union {
		Object *obj;       // error or return value, for CODE_FS_VALUERETURN and CODE_FS_ERROR
		size_t jumpidx;    // for CODE_FS_JUMP
	} val;
};

bool runner_init(struct Runner *rnr, Interp *interp, const struct Code *code)
{
	size_t n = (size_t)code->nlocalvars + (size_t)code->maxstacksz;
	if (n == 0)
		rnr->locals = rnr->stackbot = NULL;
	else {
		if (!( rnr->locals = malloc(sizeof(rnr->locals[0]) * n) )) {
			errobj_set_nomem(interp);
			return false;
		}

		memset(rnr->locals, 0, sizeof(rnr->locals[0]) * code->nlocalvars);
		rnr->stackbot = rnr->locals + code->nlocalvars;
	}

	// from now on, everything will succeed
	rnr->interp = interp;
	rnr->stacktop = rnr->stackbot;
	dynarray_init(&rnr->ehstack);
	dynarray_init(&rnr->fsstack);
	rnr->code = code;
	rnr->opidx = 0;
	rnr->retval = NULL;

	return true;
}

static void destroy_finally_state(struct RunnerFinallyState fs)
{
	if (fs.kind == CODE_FS_ERROR || fs.kind == CODE_FS_VALUERETURN)
		OBJECT_DECREF(fs.val.obj);
}

void runner_free(const struct Runner *rnr)
{
	assert(rnr->stacktop == rnr->stackbot);   // stack is empty
	assert(rnr->ehstack.len == 0);
	assert(rnr->fsstack.len == 0);

	// locals and stack are part of same block
	for (Object **ptr = rnr->locals; ptr < rnr->stackbot; ptr++)
		if (*ptr)
			OBJECT_DECREF(*ptr);
	free(rnr->locals);     

	free(rnr->ehstack.ptr);
	free(rnr->fsstack.ptr);
}


static bool run_constant(struct Runner *rnr, const struct CodeOp *op)
{
	OBJECT_INCREF(op->data.obj);
	*rnr->stacktop++ = op->data.obj;
	rnr->opidx++;
	return true;
}

static bool run_setattr(struct Runner *rnr, const struct CodeOp *op)
{
	assert(rnr->stacktop - rnr->stackbot >= 2);
	AsdaInstObject *sethere = (AsdaInstObject *) *--rnr->stacktop;
	Object *val = *--rnr->stacktop;

	assert(sethere->type->kind == TYPE_ASDACLASS);
	assert(sethere->type == op->data.attr.type);

	size_t i = op->data.attr.index;
	assert(sethere->type->attrs[i].kind == TYPE_ATTR_ASDA);

	if (sethere->attrvals[i])
		OBJECT_DECREF(sethere->attrvals[i]);
	sethere->attrvals[i] = val;

	OBJECT_DECREF(sethere);
	rnr->opidx++;
	return true;
}

static bool run_getattr(struct Runner *rnr, const struct CodeOp *op)
{
	assert(rnr->stacktop > rnr->stackbot);
	Object **ptr = rnr->stacktop - 1;
	assert((*ptr)->type == op->data.attr.type);

	struct TypeAttr attr = (*ptr)->type->attrs[op->data.attr.index];
	Object *res;

	switch(attr.kind) {

	case TYPE_ATTR_ASDA:
		assert((*ptr)->type->kind == TYPE_ASDACLASS);
		res = ((AsdaInstObject *) *ptr)->attrvals[op->data.attr.index];
		if (!res) {
			// TODO: "AttrError" class or something
			// TODO: include attribute name in error message somehow
			errobj_set(rnr->interp, &errobj_type_value, "value of an attribute has not been set");
			return false;
		}
		OBJECT_INCREF(res);
		break;

	case TYPE_ATTR_METHOD:
		assert(attr.method);
		res = (Object *) partialfunc_create(rnr->interp, attr.method, ptr, 1);
		if (!res)
			return false;
		break;

	}

	OBJECT_DECREF(*ptr);
	*ptr = res;
	rnr->opidx++;
	return true;
}

static bool run_setlocal(struct Runner *rnr, const struct CodeOp *op)
{
	Object **ptr = &rnr->locals[op->data.localvaridx];
	if (*ptr)
		OBJECT_DECREF(*ptr);
	*ptr = *--rnr->stacktop;

	rnr->opidx++;
	return true;
}

static bool run_getlocal(struct Runner *rnr, const struct CodeOp *op)
{
	Object *val = rnr->locals[op->data.localvaridx];
	OBJECT_INCREF(val);
	*rnr->stacktop++ = val;

	rnr->opidx++;
	return true;
}

static bool run_createbox(struct Runner *rnr, const struct CodeOp *op)
{
	BoxObject *box = boxobj_new(rnr->interp);
	if (!box)
		return false;
	*rnr->stacktop++ = (Object *) box;

	rnr->opidx++;
	return true;
}

static bool run_set2box(struct Runner *rnr, const struct CodeOp *op)
{
	BoxObject *box = (BoxObject*) *--rnr->stacktop;
	Object *val = *--rnr->stacktop;
	boxobj_set(box, val);
	OBJECT_DECREF(box);
	OBJECT_DECREF(val);

	rnr->opidx++;
	return true;
}

static bool run_unbox(struct Runner *rnr, const struct CodeOp *op)
{
	Object *val = ((BoxObject *) rnr->stacktop[-1])->val;
	OBJECT_DECREF(rnr->stacktop[-1]);
	OBJECT_INCREF(val);
	rnr->stacktop[-1] = val;

	rnr->opidx++;
	return true;
}

static bool run_getfrommodule(struct Runner *rnr, const struct CodeOp *op)
{
	Object *val = *op->data.modmemberptr;
	if (!val) {
		errobj_set(rnr->interp, &errobj_type_variable, "value of an exported variable hasn't been set");
		return false;
	}

	OBJECT_INCREF(val);
	*rnr->stacktop++ = val;
	rnr->opidx++;
	return true;
}

static bool run_callfunc(struct Runner *rnr, const struct CodeOp *op)
{
	size_t nargs = op->data.func_nargs;
	assert(rnr->stacktop - rnr->stackbot >= (long)nargs + 1);   // +1 for the function
	rnr->stacktop -= nargs;
	Object **argptr = rnr->stacktop;
	FuncObject *func = (FuncObject *) *--rnr->stacktop;

	Object *result;
	bool ok = funcobj_call(rnr->interp, func, argptr, nargs, &result);

	OBJECT_DECREF(func);
	for(size_t i=0; i < nargs; i++) OBJECT_DECREF(argptr[i]);
	if (!ok)
		return false;

	if (result)
		*rnr->stacktop++ = result;
	rnr->opidx++;
	return true;
}

static bool run_callconstructor(struct Runner *rnr, const struct CodeOp *op)
{
	const struct Type *t = op->data.constructor.type;
	size_t nargs = op->data.constructor.nargs;

	assert(rnr->stacktop - rnr->stackbot >= (long)nargs);
	rnr->stacktop -= nargs;
	Object **argptr = rnr->stacktop;

	assert(t->constructor);
	Object *obj = t->constructor(rnr->interp, t, argptr, nargs);
	for(size_t i=0; i < nargs; i++)
		OBJECT_DECREF(argptr[i]);
	if (!obj)
		return false;

	assert(obj->type == t);

	*rnr->stacktop++ = obj;
	rnr->opidx++;
	return true;
}

static bool run_jump(struct Runner *rnr, const struct CodeOp *op)
{
	rnr->opidx = op->data.jump_idx;
	return true;
}

static bool run_jumpif(struct Runner *rnr, const struct CodeOp *op)
{
	BoolObject *obj = (BoolObject *) *--rnr->stacktop;
	bool b = boolobj_asda2c(obj);
	OBJECT_DECREF(obj);
	if (b)
		rnr->opidx = op->data.jump_idx;
	else
		rnr->opidx++;
	return true;
}

static bool run_jumpifeq(struct Runner *rnr, const struct CodeOp *op)
{
	IntObject *x = (IntObject *)*--rnr->stacktop;
	IntObject *y = (IntObject *)*--rnr->stacktop;

	if (intobj_cmp(x, y) == 0)
		rnr->opidx = op->data.jump_idx;
	else
		rnr->opidx++;

	OBJECT_DECREF(x);
	OBJECT_DECREF(y);
	return true;
}

static bool run_strjoin(struct Runner *rnr, const struct CodeOp *op)
{
	DEBUG_PRINTF("string join of %zu strings\n", (size_t)op->data.strjoin_nstrs);
	assert(rnr->stacktop - rnr->stackbot >= op->data.strjoin_nstrs);

	Object **ptr = rnr->stacktop - op->data.strjoin_nstrs;
	StringObject *res = stringobj_join(rnr->interp, (StringObject **)ptr, op->data.strjoin_nstrs);
	if(!res)
		return false;

	for (; ptr < rnr->stacktop; ptr++)
		OBJECT_DECREF(*ptr);

	rnr->stacktop -= op->data.strjoin_nstrs;
	*rnr->stacktop++ = (Object *)res;

	rnr->opidx++;
	return true;
}

static bool run_pop1(struct Runner *rnr, const struct CodeOp *op)
{
	Object *obj = *--rnr->stacktop;
	OBJECT_DECREF(obj);
	rnr->opidx++;
	return true;
}

static bool run_createfunc(struct Runner *rnr, const struct CodeOp *op)
{
	FuncObject *f = asdafunc_create(rnr->interp, op->data.createfunc.type, &op->data.createfunc.code);
	if (!f)
		return false;

	*rnr->stacktop++ = (Object *)f;
	rnr->opidx++;
	return true;
}

static bool run_createpartial(struct Runner *rnr, const struct CodeOp *op)
{
	FuncObject *f = (FuncObject *) rnr->stacktop[-1];
	Object **args = rnr->stacktop - 1 - op->data.func_nargs;
	FuncObject *par = partialfunc_create(rnr->interp, f, args, op->data.func_nargs);
	if (!par)
		return false;

	for (long i = -1L - op->data.func_nargs; i < 0; i++)
		OBJECT_DECREF(rnr->stacktop[i]);
	rnr->stacktop -= op->data.func_nargs;
	rnr->stacktop[-1] = (Object *) par;

	rnr->opidx++;
	return true;
}

static bool run_storeretval(struct Runner *rnr, const struct CodeOp *op)
{
	assert(!rnr->retval);
	rnr->retval = *--rnr->stacktop;
	rnr->opidx++;
	return true;
}

static bool run_throw(struct Runner *rnr, const struct CodeOp *op)
{
	Object *e = *--rnr->stacktop;
	errobj_set_obj(rnr->interp, (ErrObject *)e);
	OBJECT_DECREF(e);
	return false;
}

static bool run_setmethods2class(struct Runner *rnr, const struct CodeOp *op)
{
	const struct TypeAsdaClass *type = op->data.setmethods.type;
	assert(type->nasdaattrs + op->data.setmethods.nmethods == type->nattrs);
	assert(rnr->stacktop - rnr->stackbot >= op->data.setmethods.nmethods);

	// TODO: write the loop nicer? this isn't performance critical code though
	Object **ptr = rnr->stacktop - op->data.setmethods.nmethods;
	for (size_t i = type->nasdaattrs; i < type->nattrs; i++) {
		assert(type->attrs[i].kind == TYPE_ATTR_METHOD);
		assert(!type->attrs[i].method);
		type->attrs[i].method = (FuncObject *) *ptr++;
	}
	rnr->stacktop -= op->data.setmethods.nmethods;

	rnr->opidx++;
	return true;
}

static bool run_fs_push_something(struct Runner *rnr, const struct CodeOp *op)
{
	struct RunnerFinallyState fs;
	fs.kind = op->kind;
	if (op->kind == CODE_FS_ERROR || op->kind == CODE_FS_VALUERETURN)
		fs.val.obj = *--rnr->stacktop;
	if (op->kind == CODE_FS_VALUERETURN)
		fs.val.jumpidx = op->data.jump_idx;

	if (!dynarray_push(rnr->interp, &rnr->fsstack, fs)) {
		destroy_finally_state(fs);
		return false;
	}
	rnr->opidx++;
	return true;
}

static bool run_fs_apply(struct Runner *rnr, const struct CodeOp *op)
{
	struct RunnerFinallyState fs = dynarray_pop(&rnr->fsstack);

	bool r;
	switch (fs.kind) {
		case CODE_FS_OK:
			r = true;
			rnr->opidx++;
			break;
		case CODE_FS_ERROR:
			r = false;
			errobj_set_obj(rnr->interp, (ErrObject *)fs.val.obj);
			break;

		case CODE_FS_VALUERETURN:
			r = true;
			assert(!rnr->retval);
			rnr->retval = fs.val.obj;
			OBJECT_INCREF(rnr->retval);
			break;
		case CODE_FS_JUMP:
			r = true;
			rnr->opidx = fs.val.jumpidx;
			break;
		default:
			assert(0);
			break;
	}

	destroy_finally_state(fs);
	return r;
}

static bool run_fs_discard(struct Runner *rnr, const struct CodeOp *op)
{
	struct RunnerFinallyState fs = dynarray_pop(&rnr->fsstack);
	destroy_finally_state(fs);
	rnr->opidx++;
	return true;
}

static bool run_eh_add(struct Runner *rnr, const struct CodeOp *op)
{
	if (!dynarray_push(rnr->interp, &rnr->ehstack, op->data.errhnd))
		return false;
	rnr->opidx++;
	return true;
}

static bool run_eh_rm(struct Runner *rnr, const struct CodeOp *op)
{
	(void) dynarray_pop(&rnr->ehstack);
	rnr->opidx++;
	return true;
}

static bool run_integer_binary_operation(struct Runner *rnr, const struct CodeOp *op)
{
	assert(rnr->stacktop - rnr->stackbot >= 2);
	// y before x because the stack is like this:
	//
	//   |---|---|---|---|---|---|---|---|---|
	//   | stuff we don't care about | x | y |
	IntObject *y = (IntObject *)*--rnr->stacktop;
	IntObject *x = (IntObject *)*--rnr->stacktop;
	IntObject *res;

	switch(op->kind) {
		case CODE_INT_ADD: res = intobj_add(rnr->interp, x, y); break;
		case CODE_INT_SUB: res = intobj_sub(rnr->interp, x, y); break;
		case CODE_INT_MUL: res = intobj_mul(rnr->interp, x, y); break;
		default: assert(0);
	}
	OBJECT_DECREF(x);
	OBJECT_DECREF(y);

	if(!res)
		return false;
	*rnr->stacktop++ = (Object *)res;
	rnr->opidx++;
	return true;
}

static bool run_int_neg(struct Runner *rnr, const struct CodeOp *op)
{
	assert(rnr->stacktop > rnr->stackbot);
	IntObject **ptr = (IntObject **)(rnr->stacktop - 1);
	IntObject *obj = intobj_neg(rnr->interp, *ptr);
	if(!obj)
		return false;
	OBJECT_DECREF(*ptr);
	*ptr = obj;

	rnr->opidx++;
	return true;
}


static bool run_one_op(struct Runner *rnr, const struct CodeOp *op)
{
	//codeop_debug(op);
	switch(op->kind) {
	#define BOILERPLATE(CONSTANT, FUNC) case (CONSTANT): return (FUNC)(rnr, op)
		BOILERPLATE(CODE_CONSTANT, run_constant);
		BOILERPLATE(CODE_SETATTR, run_setattr);
		BOILERPLATE(CODE_GETATTR, run_getattr);
		BOILERPLATE(CODE_SETLOCAL, run_setlocal);
		BOILERPLATE(CODE_GETLOCAL, run_getlocal);
		BOILERPLATE(CODE_CREATEBOX, run_createbox);
		BOILERPLATE(CODE_SET2BOX, run_set2box);
		BOILERPLATE(CODE_UNBOX, run_unbox);
		BOILERPLATE(CODE_GETFROMMODULE, run_getfrommodule);
		BOILERPLATE(CODE_CALLFUNC, run_callfunc);
		BOILERPLATE(CODE_CALLCONSTRUCTOR, run_callconstructor);
		BOILERPLATE(CODE_JUMP, run_jump);
		BOILERPLATE(CODE_JUMPIF, run_jumpif);
		BOILERPLATE(CODE_JUMPIFEQ, run_jumpifeq);
		BOILERPLATE(CODE_STRJOIN, run_strjoin);
		BOILERPLATE(CODE_POP1, run_pop1);
		BOILERPLATE(CODE_THROW, run_throw);
		BOILERPLATE(CODE_CREATEFUNC, run_createfunc);
		BOILERPLATE(CODE_CREATEPARTIAL, run_createpartial);
		BOILERPLATE(CODE_STORERETVAL, run_storeretval);
		BOILERPLATE(CODE_SETMETHODS2CLASS, run_setmethods2class);
		BOILERPLATE(CODE_EH_ADD, run_eh_add);
		BOILERPLATE(CODE_EH_RM, run_eh_rm);
		BOILERPLATE(CODE_FS_OK, run_fs_push_something);
		BOILERPLATE(CODE_FS_ERROR, run_fs_push_something);
		BOILERPLATE(CODE_FS_VALUERETURN, run_fs_push_something);
		BOILERPLATE(CODE_FS_JUMP, run_fs_push_something);
		BOILERPLATE(CODE_FS_APPLY, run_fs_apply);
		BOILERPLATE(CODE_FS_DISCARD, run_fs_discard);
		BOILERPLATE(CODE_INT_ADD, run_integer_binary_operation);
		BOILERPLATE(CODE_INT_SUB, run_integer_binary_operation);
		BOILERPLATE(CODE_INT_MUL, run_integer_binary_operation);
		BOILERPLATE(CODE_INT_NEG, run_int_neg);
	#undef BOILERPLATE
	}

	// never runs, silences compiler warning
	return true;
}


// returns NULL for nothing found (that's not an error)
// discards checked error handlers, including the possible matching one
// leaves other error handlers there because they could catch other errors later
static const struct CodeErrHndItem *find_matching_error_handler_item(struct Runner *rnr)
{
	assert(rnr->interp->err);
	for (long i = (long)rnr->ehstack.len - 1; i >= 0; i--) {
		struct CodeErrHnd eh = rnr->ehstack.ptr[i];
		for (size_t k = 0; k < eh.len; k++) {
			if (type_compatiblewith(rnr->interp->err->type, eh.arr[k].errtype)) {
				rnr->ehstack.len = (size_t)i;
				return &eh.arr[k];
			}
		}
	}

	rnr->ehstack.len = 0;
	return NULL;
}

// TODO
static void jump_to_error_handler(struct Runner *rnr, struct CodeErrHndItem ehi)
{
/*
	rnr->opidx = ehi.jmpidx;

	struct ErrObject *e = rnr->interp->err;
	assert(e);

	if (rnr->scope->locals[ehi.errvar])
		OBJECT_DECREF(rnr->scope->locals[ehi.errvar]);
	rnr->scope->locals[ehi.errvar] = (Object *)e;
	rnr->interp->err = NULL;

	errobj_beginhandling(rnr->interp, e);
*/
	assert(0);
}

static void clear_stack(struct Runner *rnr)
{
	assert(rnr->stacktop >= rnr->stackbot);
	for (long i = 0; i < rnr->stacktop - rnr->stackbot; i++)
		OBJECT_DECREF(rnr->stackbot[i]);
	rnr->stacktop = rnr->stackbot;
}

bool runner_run(struct Runner *rnr)
{
	struct InterpStackItem tmp;
	tmp.srcpath = rnr->code->srcpath;
	// lineno set soon

	if (!dynarray_push(rnr->interp, &rnr->interp->stack, tmp))
		return false;

	size_t interpstackidx = rnr->interp->stack.len - 1;
	bool ok;

	while (rnr->opidx < rnr->code->nops) {
		const struct CodeOp *op = &rnr->code->ops[rnr->opidx];
		rnr->interp->stack.ptr[interpstackidx].lineno = op->lineno;

		//codeop_debug(op);
		ok = run_one_op(rnr, op);
		if (!ok) {
			if (rnr->retval) {
				OBJECT_DECREF(rnr->retval);
				rnr->retval = NULL;
			}

			clear_stack(rnr);
			const struct CodeErrHndItem *ehi = find_matching_error_handler_item(rnr);
			if (ehi) {
				jump_to_error_handler(rnr, *ehi);
				continue;
			}
			goto out;
		}
	}

	assert(rnr->opidx == rnr->code->nops);
	ok = true;
	// "fall through"

out:
	assert(interpstackidx == rnr->interp->stack.len - 1);
	struct InterpStackItem pop = dynarray_pop(&rnr->interp->stack);
	assert(pop.srcpath == rnr->code->srcpath);
	return ok;
}
