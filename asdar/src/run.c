#include "run.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include "builtin.h"
#include "code.h"
#include "dynarray.h"
#include "interp.h"
#include "object.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "stacktrace.h"


//#define DEBUG(...) printf(__VA_ARGS__)
#define DEBUG(...) (void)0


#define ARRAY_COPY(DST, SRC, N) do{ \
	assert( sizeof((SRC)[0]) == sizeof((DST)[0]) ); \
	memcpy((DST), (SRC), (N)*sizeof((SRC)[0])); \
} while(0)

static void swap(Object **a, Object **b)
{
	Object *tmp = *a;
	*a = *b;
	*b = tmp;
}


struct State {
	/*
	Pointers into interp->code. Assumes that interp->code.ptr isn't reallocated
	when running, i.e. no more importing once we start running stuff. This is used
	for returning and error messages.
	*/
	DynArray(const struct CodeOp *) callstack;

	/*
	local variables, function arguments etc. Not cleared completely when a function
	is called, but each function call cleans up after (except for the possible
	return value).
	*/
	DynArray(struct Object *) objstack;

	/*
	The purpose of this is that when an error happens while handling another
	error, both errors are shown in the error message. For example, let's say
	that error1 happens. Then while handling that, we get error2, and while
	handling error2 we get error3. Then, if no code wants to handle error3, we
	end up with error3 in interp->err and the other two errors in errstack.

	However, errobj_set and friends take only the interp as an argument, which is
	convenient. So, the error object first goes to interp->err and then here.
	*/
	DynArray(struct StackTrace) errstack;
};

static bool init_state(struct State *state, Interp *interp)
{
	dynarray_init(&state->callstack);
	dynarray_init(&state->objstack);
	dynarray_init(&state->errstack);

	// there must be always room for one more error to occur
	return dynarray_alloc(interp, &state->errstack, 1);
}

static void deinit_state(struct State *state)
{
	// TODO: can objects be left here?
	while (state->objstack.len != 0) {
		Object *obj = dynarray_pop(&state->objstack);
		OBJECT_DECREF(obj);
	}

	free(state->callstack.ptr);
	free(state->objstack.ptr);
	free(state->errstack.ptr);
}

/*
When setting an error, the error setting functions don't know which part of the
code was actually running when the error occured. That's why this is here.
*/
static void set_error_info(Interp *interp, struct State *state, const struct CodeOp *op)
{
	ErrObject *err = interp->err;
	interp->err = NULL;

	dynarray_push_itwillfit(&state->errstack, (struct StackTrace){0});
	struct StackTrace *strace = &state->errstack.ptr[state->errstack.len - 1];

	strace->errobj = err;
	strace->op = op;

	size_t maxlen = sizeof(strace->callstack) / sizeof(strace->callstack[0]);
	assert(maxlen % 2 == 0);

	if (state->callstack.len > maxlen) {
		strace->callstacklen = maxlen;
		strace->callstackskip = state->callstack.len - maxlen;
		ARRAY_COPY(strace->callstack, state->callstack.ptr, maxlen/2);
		ARRAY_COPY(strace->callstack + maxlen/2, state->callstack.ptr + state->callstack.len - maxlen/2, maxlen/2);
	} else {
		strace->callstacklen = state->callstack.len;
		strace->callstackskip = 0;
		ARRAY_COPY(strace->callstack, state->callstack.ptr, state->callstack.len);
	}
}

static bool begin_try(Interp *interp, struct State *state)
{
	/*
	There must be enough room for 2 errors, because we can have an error in try
	and then another error while handling that in 'catch'.

	FIXME: this should allocate room for more than 2 errors with nested trys
	*/
	return dynarray_alloc(interp, &state->errstack, state->errstack.len + 2);
}


// TODO: look into python's new vectorcall stuff
static bool call_builtin_function(Interp *interp, struct State *state, const struct BuiltinFunc *bfunc)
{
	assert(state->objstack.len >= bfunc->nargs);
	assert(&builtin_funcs[0] <= bfunc && bfunc < &builtin_funcs[builtin_nfuncs]);

	bool ret = bfunc->ret;   // makes the compiler understand enough to not do warning
	Object **args = &state->objstack.ptr[state->objstack.len - bfunc->nargs];
	Object *retobj;
	bool ok;

	if (ret)
		ok = !!( retobj = bfunc->func.ret(interp, args) );
	else
		ok = bfunc->func.noret(interp, args);

	for (size_t i = 0; i < bfunc->nargs; i++)
		OBJECT_DECREF(args[i]);
	state->objstack.len -= bfunc->nargs;

	if (!ok)
		return false;

	if (ret){
		if (!dynarray_push(interp, &state->objstack, retobj)) {
			OBJECT_DECREF(retobj);
			return false;
		}
	}

	return true;
}

bool run(Interp *interp, size_t startidx)
{
	struct State state;
	if (!init_state(&state, interp))
		return false;
	const struct CodeOp *ptr = &interp->code.ptr[startidx];

	while(true){
		DEBUG("start=%p ptr=start+%p diff=%d\n",
			(void*)interp->code.ptr,
			(void*)ptr,
			(int)(ptr - interp->code.ptr));
		assert(interp->code.ptr <= ptr && ptr < &interp->code.ptr[interp->code.len]);

		size_t sz;
		Object *obj;

		switch(ptr->kind) {
		case CODE_CONSTANT:
			if (!dynarray_push(interp, &state.objstack, ptr->data.obj))
				goto error;
			OBJECT_INCREF(ptr->data.obj);
			ptr++;
			break;

		case CODE_CALLBUILTINFUNC:
			if (!call_builtin_function(interp, &state, ptr->data.builtinfunc))
				goto error;
			ptr++;
			break;

		case CODE_CALLCODEFUNC:
			if (!dynarray_push(interp, &state.callstack, ptr))
				goto error;
			// fall through
		case CODE_JUMP:
			ptr = &interp->code.ptr[ptr->data.call.jump];
			break;

		case CODE_RETURN:
			if (state.callstack.len == 0) {
				DEBUG("return and no more callstack, so we are done\n");
				assert(state.objstack.len == 0);
				deinit_state(&state);
				return true;
			}
			ptr = dynarray_pop(&state.callstack) + 1;
			break;

		case CODE_THROW:
			errobj_set(interp, &errtype_value, "oh no");			// TODO
			goto error;

		case CODE_SWAP:
			swap(
				&state.objstack.ptr[state.objstack.len - ptr->data.swap.index1 - 1],
				&state.objstack.ptr[state.objstack.len - ptr->data.swap.index2 - 1]);
			ptr++;
			break;

		case CODE_DUP:
			obj = state.objstack.ptr[state.objstack.len - ptr->data.objstackidx - 1];
			if (!dynarray_push(interp, &state.objstack, obj))
				goto error;
			OBJECT_INCREF(obj);
			ptr++;
			break;

		case CODE_JUMPIF:
			obj = dynarray_pop(&state.objstack);
			if (boolobj_asda2c((BoolObject *) obj))
				ptr = &interp->code.ptr[ptr->data.jump];
			else
				ptr++;
			OBJECT_DECREF(obj);
			break;

		default:
			printf("TODO: ");
			codeop_debug(ptr->kind);
			ptr++;
			break;
		}
	}

error:
	set_error_info(interp, &state, ptr);

	// TODO: look for 'try' blocks

	for (size_t i = 0; i < state.errstack.len; i++) {
		if (i)
			fprintf(stderr, "\nAnother error happened while handling the above error:\n\n");
		stacktrace_print(interp, &state.errstack.ptr[i]);
		OBJECT_DECREF(state.errstack.ptr[i].errobj);
	}

	deinit_state(&state);
	return false;
}
