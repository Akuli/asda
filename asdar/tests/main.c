#include <assert.h>
#include <src/interp.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

struct TestList {
	int ntests;   // -1 for run everything
	const char **testnames;
};

// returns whether to run the test
static bool test_should_run(struct TestList *tl, const char *name)
{
	if (tl->ntests < 0)
		return true;

	for (int i = 0; i < tl->ntests; i++) {
		if (strcmp(tl->testnames[i], name) == 0) {
			tl->testnames[i] = tl->testnames[--tl->ntests];
			return true;
		}
	}
	return false;
}


// usage:  ./testrunner [testname1, testname2, ...]
int main(int argc, char **argv)
{
	struct TestList tl;

	if (argc <= 1) {
		tl.ntests = -1;
		tl.testnames = NULL;
	} else {
		// check for any arguments that don't look like tests
		for (int i = 1; i < argc; i++)
			if (argv[i][0] == '-') {
				fprintf(stderr, "Usage: %s [testname1 testname2 ...]\n", argv[0]);
				return 2;
			}

		tl.ntests = argc-1;
		tl.testnames = malloc(sizeof(tl.testnames[0]) * (unsigned)tl.ntests);
		assert(tl.testnames);
		memcpy(tl.testnames, argv+1, (unsigned)(argc-1) * sizeof(argv[0]));
	}

	Interp interp;
	interp_init(&interp, "argv0 test value");

#define RUN_TEST(NAME) do{ \
	if (test_should_run(&tl, #NAME)) { \
		printf("  Running test: %s\n", #NAME); \
		void test_##NAME(Interp *); \
		test_##NAME(&interp); \
		assert(!interp.err); \
	} \
} while(0)
#include "runcalls.h"

	for (int i = 0; i < tl.ntests; i++)
		fprintf(stderr, "%s: WARNING: unknown test '%s'\n", argv[0], tl.testnames[i]);

	interp_destroy(&interp);
	free(tl.testnames);
}
