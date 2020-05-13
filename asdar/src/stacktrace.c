#include "stacktrace.h"
#include <stdio.h>
#include <stdlib.h>
#include "code.h"
#include "path.h"


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

static void print_op_stuff(const char *basedir, const char *word, const struct CodeOp *op)
{
	char *fullpath = NULL;
	if (basedir) {
		// TODO: figure out how to do this without symlink issues and ".."
		fullpath = path_concat_dotdot(basedir, op->srcpath);   // may be NULL
	}

	fprintf(stderr, "  %s file \"%s\", line %zu\n    ",
		word, (fullpath ? fullpath : op->srcpath), op->lineno);

	if (!print_source_line(fullpath, op->lineno))
		fprintf(stderr, "(error while reading source file)\n");

	free(fullpath);
}

void stacktrace_print_raw(ErrObject *err)
{
	fprintf(stderr, "%s: ", err->type->name);

	// TODO: create a stringobj_toutf8 that doesn't do mallocs
	const char *msg;
	size_t len;
	bool ok = stringobj_toutf8(err->msgstr, &msg, &len);
	assert(ok);   // FIXME
	fwrite(msg, 1, len, stderr);
	fprintf(stderr, "\n");
}

void stacktrace_print(Interp *interp, const struct StackTrace *st)
{
	stacktrace_print_raw(st->errobj);

	print_op_stuff(interp->basedir, "at", st->op);
	for (long i = (long)st->callstacklen - 1; i >= 0; i--) {
		if (st->callstackskip != 0 &&
			i == ( sizeof(st->callstack)/sizeof(st->callstack[0]) )/2)
		{
			fprintf(stderr, "...%zu items more...\n", st->callstackskip);
		}
		print_op_stuff(interp->basedir, "by", st->callstack[i]);
	}
}
