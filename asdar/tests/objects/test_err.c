#include <assert.h>
#include <errno.h>
#include <stddef.h>
#include <stdio.h>
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

TEST(errobj_set_oserr)
{
	char msg[200];
	sprintf(msg, "cannot open '/path/to/file.txt': No such file or directory (errno %d)", ENOENT);

	errno = ENOENT;
	errobj_set_oserr(interp, "cannot open '%s'", "/path/to/file.txt");
	assert_error_matches_and_clear(interp, &errobj_type_os, msg);

	errno = 0;
	errobj_set_oserr(interp, "cannot open '%s'", "/path/to/file.txt");
	assert_error_matches_and_clear(interp, &errobj_type_os, "cannot open '/path/to/file.txt'");
}
