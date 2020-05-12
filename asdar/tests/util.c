#include "util.h"
#include <assert.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <src/dynarray.h>
#include <src/interp.h>
#include <src/object.h>
#include <src/type.h>
#include <src/objects/err.h>
#include <src/objects/string.h>

void assert_cstr_eq_cstr(const char *s1, const char *s2)
{
	if (strcmp(s1, s2) != 0) {
		fprintf(stderr, "strings are not equal\n");
		fprintf(stderr, "first string:  (%zu) %s\n", strlen(s1), s1);
		fprintf(stderr, "second string: (%zu) %s\n", strlen(s2), s2);
		abort();
	}
}

void assert_strobj_eq_cstr(StringObject *obj, const char *s)
{
	const char *objstr;
	size_t junk;
	bool ok = stringobj_toutf8(obj, &objstr, &junk);
	assert(ok);
	assert_cstr_eq_cstr(objstr, s);
}

void assert_error_matches_and_clear(Interp *interp, const struct Type *errtype, const char *cstr)
{
	assert(interp->errstack.len == 1);
	ErrObject *err = dynarray_pop(&interp->errstack);
	assert(err->type == errtype);

	if (errtype == &errtype_nomem)
		assert(err->refcount == 2);   // nomemerr is stored in a static variable
	else
		assert(err->refcount == 1);
	assert_strobj_eq_cstr(err->msgstr, cstr);

	OBJECT_DECREF(err);
}
