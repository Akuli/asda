#ifndef TESTS_UTIL_H
#define TESTS_UTIL_H

// stdio.h is here to allow debugging tests by adding printf
#include <stdio.h>   // IWYU pragma: keep
#include <src/interp.h>
#include <src/objtyp.h>
#include <src/objects/string.h>

#define TEST(NAME) void test_##NAME(Interp *interp)

void assert_cstr_eq_cstr(const char *s1, const char *s2);
void assert_strobj_eq_cstr(struct StringObject *obj, const char *s);
void assert_error_matches_and_clear(Interp *interp, const struct Type *errtype, const char *cstr);

#endif   // TESTS_UTIL_H
