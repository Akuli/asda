#include <src/interp.h>
#include <stdio.h>
#include "util.h"

#define RUN_TESTS(NAME) do{ \
	printf("----- %s.c -----\n", #NAME); \
	extern const struct Test tests_##NAME[]; \
	for (size_t i = 0; tests_##NAME[i].f; i++) { \
		printf("%s\n", tests_##NAME[i].name); \
		tests_##NAME[i].f(&interp); \
	} \
} while(0)


int main(void)
{
	Interp interp;
#include "runcalls.h"
}
