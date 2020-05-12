#include <assert.h>
#include <stdio.h>
#include <stdlib.h>
#include "code.h"
#include "import.h"
#include "interp.h"
#include "path.h"
#include "objects/err.h"


static bool print_source_line(const char *path, size_t lineno)
{
	FILE *f = fopen(path, "r");
	if (!f)
		return false;

	int c;

	while (--lineno) {
		// skip line
		while ((c = fgetc(f)) != EOF && c != '\n')
			;
		if (c == EOF) {
			fclose(f);
			return false;
		}
	}

	// skip spaces
	c = EOF;
	while ((c = getc(f)) == ' ')
		;
	if (c != EOF)
		ungetc(c, f);

	while ((c = fgetc(f)) != EOF && c != '\n')
		putc(c, stderr);
	putc('\n', stderr);

	fclose(f);
	return true;
}

// iesi = InterpErrStackItem
static void print_stack_of_iesi(const char *basedir, struct InterpErrStackItem iesi)
{
	fprintf(stderr, "%s: ", iesi.errobj->type->name);

	// TODO: create a stringobj_toutf8 that doesn't do mallocs
	const char *msg;
	size_t len;
	bool ok = stringobj_toutf8(iesi.errobj->msgstr, &msg, &len);
	assert(ok);   // FIXME
	fwrite(msg, 1, len, stderr);
	fprintf(stderr, "\n");

	for (long i = (long)iesi.callstacklen - 1; i >= 0; i--) {
		if (iesi.callstackskip != 0 &&
			i == ( sizeof(iesi.callstack)/sizeof(iesi.callstack[0]) )/2)
		{
			fprintf(stderr, "...%zu items more...\n", iesi.callstackskip);
		}

		const struct CodeOp *op = iesi.callstack[i];

		// TODO: figure out how to do this without symlink issues and ".."
		char *fullpath = NULL;
		if (basedir)
			fullpath = path_concat_dotdot(basedir, op->srcpath);   // may be NULL

		const char *word = (i == (long)iesi.callstacklen - 1) ? "in" : "by";
		if (fullpath)
			fprintf(stderr, "  %s file \"%s\"", word, fullpath);
		else
			fprintf(stderr, "  %s file \"%s\" (could not get full path)", word, op->srcpath);
		fprintf(stderr, ", line %zu\n    ", op->lineno);

		if (!print_source_line(fullpath, op->lineno))
			printf("(error while reading source file)\n");

		free(fullpath);
	}
}


int main(int argc, char **argv)
{
	char *basedir = NULL;

	if (argc != 2) {
		fprintf(stderr, "Usage: %s bytecodefile\n", argv[0]);
		return 2;
	}

	Interp interp;
	if (!interp_init(&interp, argv[0])) {
		fprintf(stderr, "interp_init: not enough memory\n");
		return 1;
	};

	if (!( basedir = path_toabsolute(argv[1]) )) {
		errobj_set_oserr(&interp, "finding absolute path of '%s' failed", argv[1]);
		goto error;
	}

	size_t i = path_findlastslash(basedir);
	basedir[i] = 0;
	interp.basedir = basedir;
	const char *relative = basedir + (i+1);

	if (!import(&interp, relative))
		goto error;

	free(basedir);
	interp_destroy(&interp);

	return 0;

error:
	assert(interp.errstack.len >= 1);
	for (size_t i = 0; i < interp.errstack.len; i++) {
		if (i != 0)
			fprintf(stderr, "\nGot another error while handling the above error:\n");
		print_stack_of_iesi(basedir, interp.errstack.ptr[i]);
		OBJECT_DECREF(interp.errstack.ptr[i].errobj);
	}

	free(basedir);
	interp_destroy(&interp);
	return 1;
}
