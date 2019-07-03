#ifndef TESTS_UTIL_H
#define TESTS_UTIL_H

// to allow debugging tests by adding printf
#include <stdio.h>   // IWYU pragma: keep

#include <src/interp.h>

#define TEST(NAME) void test_##NAME(Interp *interp)

#endif   // TESTS_UTIL_H
