#include <assert.h>
#include <src/interp.h>
#include <stdio.h>
#include "util.h"

#define RUN_TEST(NAME) do{ \
	printf("  Running test: %s\n", #NAME); \
	void test_##NAME(Interp *); \
	test_##NAME(&interp); \
} while(0)


int main(void)
{
	Interp interp;
	bool ok = interp_init(&interp, "argv0 test value");
	assert(ok);
#include "runcalls.h"
	interp_destroy(&interp);
}
