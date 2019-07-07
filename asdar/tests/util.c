#include "util.h"
#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
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

void assert_strobj_eq_cstr(Object *obj, const char *s)
{
	const char *objstr;
	size_t junk;
	bool ok = stringobj_toutf8(obj, &objstr, &junk);
	assert(ok);
	assert_cstr_eq_cstr(objstr, s);
}
