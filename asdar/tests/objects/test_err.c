#include <assert.h>
#include <stddef.h>
#include <string.h>
#include <src/interp.h>
#include <src/objects/err.h>
#include <src/objects/string.h>
#include "../util.h"


static void check_and_clear(Interp *interp, const struct Type *errtype, char *cstr)
{
	assert(interp->err);
	assert(interp->err->type == errtype);

	if (errtype == &errobj_type_nomem)
		assert(interp->err->refcount == 2);   // interp->err and wherever the global nomemerr is stored
	else
		assert(interp->err->refcount == 1);

	Object *strobj = errobj_getstring(interp->err);
	assert_strobj_eq_cstr(strobj, cstr);
	OBJECT_DECREF(strobj);

	OBJECT_DECREF(interp->err);
	interp->err = NULL;
}

TEST(errobj_set)
{
	errobj_set(interp, &errobj_type_value, "value error message %s", "lol");
	check_and_clear(interp, &errobj_type_value, "value error message lol");
}

TEST(errobj_set_nomem)
{
	assert(!interp->err);
	errobj_set_nomem(interp);
	check_and_clear(interp, &errobj_type_nomem, "not enough memory");
}

TEST(errobj_set_oserr)
{
	char msg[200];
	sprintf(msg, "cannot open '/path/to/file.txt': No such file or directory (errno %d)", ENOENT);

	errno = ENOENT;
	errobj_set_oserr(interp, "cannot open '%s'", "/path/to/file.txt");
	check_and_clear(interp, &errobj_type_os, msg);

	errno = 0;
	errobj_set_oserr(interp, "cannot open '%s'", "/path/to/file.txt");
	check_and_clear(interp, &errobj_type_os, "cannot open '/path/to/file.txt'");
}
