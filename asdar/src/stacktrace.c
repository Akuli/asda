#include "stacktrace.h"
#include <stdio.h>
#include <stdlib.h>
#include "code.h"
#include "path.h"


/*
this function is not very efficient, since it e.g. opens the same file multiple
times if called repeatedly and goes byte by byte, but that's fine for printing
stack traces
*/
static bool print_source_line(const char *path, size_t lineno)
{
	FILE *f = fopen(path, "r");
	if (!f)
		return false;

	int c;   // some valid char value or EOF

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

	// print line and '\n', even if no '\n' in the file for some reason
	while ((c = fgetc(f)) != EOF && c != '\n')
		putc(c, stderr);
	putc('\n', stderr);

	fclose(f);
	return true;
}

static void print_op_stuff(Interp *interp, const char *word, const struct CodeOp *op)
{
	struct InterpModInfo mod = interp->mods.ptr[op->modidx];
	fprintf(stderr, "  %s file \"%s\", line %zu\n    ", word, mod.srcpathabs, op->lineno);

	if (path_isnewerthan(mod.srcpathabs, mod.bcpathabs) == 1) {
		fprintf(stderr, "(source file is newer than compiled file)\n");
	} else if (!print_source_line(mod.srcpathabs, op->lineno)) {
		fprintf(stderr, "(error while reading source file)\n");
	}
}

void stacktrace_print_raw(ErrObject *err)
{
	fprintf(stderr, "%s: %s\n", err->type->name, stringobj_getutf8(err->msgstr));
}

void stacktrace_print(Interp *interp, const struct StackTrace *st)
{
	stacktrace_print_raw(st->errobj);

	print_op_stuff(interp, "at", st->op);
	for (long i = (long)st->callstacklen - 1; i >= 0; i--) {
		if (st->callstackskip != 0 &&
			i == ( sizeof(st->callstack)/sizeof(st->callstack[0]) )/2)
		{
			fprintf(stderr, "...%zu items more...\n", st->callstackskip);
		}
		print_op_stuff(interp, "by", st->callstack[i]);
	}
}
