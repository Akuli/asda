#include <stdio.h>
#include "util.h"

TEST(a)
{
	printf("path gets tested a\n");
}

TEST(b)
{
	printf("path gets tested b\n");
}


DEFINE_TESTS(path,
	DEFINE_TEST(a)
	DEFINE_TEST(b)
)
