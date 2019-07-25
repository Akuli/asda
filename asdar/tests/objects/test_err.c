#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
#include <src/dynarray.h>
#include <src/interp.h>
#include <src/objects/err.h>
#include "../util.h"


TEST(errobj_set)
{
	errobj_set(interp, &errobj_type_value, "%s %s %d %zu %B", "hello", "world", 123, (size_t)456, 'a');
	assert_error_matches_and_clear(interp, &errobj_type_value, "hello world 123 456 0x61 'a'");

	errobj_set(interp, &errobj_type_value, "this message contains %% character");
	assert_error_matches_and_clear(interp, &errobj_type_value, "this message contains % character");

	errobj_set(interp, &errobj_type_value, "%s", "this message contains % character");
	assert_error_matches_and_clear(interp, &errobj_type_value, "this message contains % character");
}

TEST(errobj_set_nomem)
{
	assert(!interp->err);
	errobj_set_nomem(interp);
	assert_error_matches_and_clear(interp, &errobj_type_nomem, "not enough memory");
}

// this test shouldn't leak memory, check with valgrind
TEST(errobj_beginhandling_memory_leak_bug)
{
	assert(interp->stack.len == 0);

	struct InterpStackItem si = { .srcpath = "Lol", .lineno = 123 };
	bool ok = dynarray_push(interp, &interp->stack, si);
	assert(ok);
	errobj_set_nomem(interp);
	(void) dynarray_pop(&interp->stack);

	ErrObject *e = interp->err;
	interp->err = NULL;

	assert(e->stacklen == 1);
	assert(e->stack == interp->stack.ptr);
	assert(!e->ownstack);
	assert(e->stack[0].srcpath == si.srcpath && e->stack[0].lineno == si.lineno);

	errobj_beginhandling(interp, e);
	assert(e->stacklen == 1);
	assert(e->stack != interp->stack.ptr);
	assert(e->ownstack);
	assert(e->stack[0].srcpath == si.srcpath && e->stack[0].lineno == si.lineno);

	OBJECT_DECREF(e);
}

TEST(errobj_set_oserr)
{
	char msg[200];
	snprintf(msg, sizeof msg, "cannot open '/path/to/file.txt': %s (errno %d)", strerror(ENOENT), ENOENT);

	errno = ENOENT;
	errobj_set_oserr(interp, "cannot open '%s'", "/path/to/file.txt");
	assert_error_matches_and_clear(interp, &errobj_type_os, msg);

	errno = 0;
	errobj_set_oserr(interp, "cannot open '%s'", "/path/to/file.txt");
	assert_error_matches_and_clear(interp, &errobj_type_os, "cannot open '/path/to/file.txt'");
}
