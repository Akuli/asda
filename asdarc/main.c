#include <errno.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bc.h"
#include "bcreader.h"
#include "path.h"

const char *misc_argv0;


int main(int argc, char **argv)
{
	misc_argv0 = argv[0];

	if (argc != 2) {
		fprintf(stderr, "Usage: %s bytecodefile\n", argv[0]);
		return 2;
	}

	struct Interp interp;
	if (!interp_init(&interp, argv[0])) {
		fprintf(stderr, "%s: not enough memory to initialize the interpreter", argv[0]);
		return 1;
	}

	char *dir = path_toabsolute(argv[1]);
	if (!dir) {
		fprintf(stderr, "%s: finding absolute path of \"%s\" failed (errno %d: %s)\n",
			argv[0], argv[1], errno, strerror(errno));
		interp_destroy(&interp);
		return 1;
	}

	size_t i = path_findlastslash(dir);
	dir[i] = 0;

	FILE *f = fopen(argv[1], "rb");
	if (!f) {
		interp_errstr_printf_errno(&interp, "cannot open %s", argv[1]);
		goto errstr_error;
	}

	char **imports = NULL;
	uint16_t nimports = 0;
	struct BcReader bcr = bcreader_new(&interp, f, dir);
	struct Bc code;

	if (!bcreader_readasdabytes(&bcr))
		goto bytecode_error;
	if (!bcreader_readimports(&bcr, &imports, &nimports))
		goto bytecode_error;
	if (!bcreader_readcodepart(&bcr, &code))
		goto bytecode_error;
	bcop_destroylist(code.firstop);

	fclose(f);
	free(dir);
	bcreader_freeimports(imports, nimports);

	return 0;

bytecode_error:
	if (imports)
		bcreader_freeimports(imports, nimports);
	fclose(f);
	// "fall through"

errstr_error:
	fprintf(stderr, "%s: error: %s\n", argv[0], interp.errstr);
	interp_destroy(&interp);
	free(dir);
	return 1;
}
