#include <assert.h>
#include <stddef.h>
#include <string.h>
#include <src/interp.h>
#include <src/objects/err.h>
#include <src/objects/string.h>
#include "../util.h"


TEST(errobj_set)
{
	errobj_set(interp, &errobj_type_value, "this message contains % character");
	assert_error_matches_and_clear(interp, &errobj_type_value, "this message contains % character");
}

TEST(errobj_set_format)
{
	errobj_set_format(interp, &errobj_type_value, "value error message %s", "lol");
	assert_error_matches_and_clear(interp, &errobj_type_value, "value error message lol");
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
