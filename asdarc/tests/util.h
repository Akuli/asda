#ifndef TESTS_UTIL_H
#define TESTS_UTIL_H

#include <src/interp.h>

struct Test {
	char *name;
	void (*f)(Interp *);
};

#define TEST(NAME) static void test_##NAME(Interp *interp)

// must NOT put commas to DEFINE_TESTS
#define DEFINE_TESTS(NAME, TESTS) const struct Test tests_##NAME[] = { TESTS {NULL,NULL} };
#define DEFINE_TEST(NAME) { #NAME, test_##NAME },


#endif   // TESTS_UTIL_H
