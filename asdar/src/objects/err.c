#include "err.h"
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "func.h"
#include "string.h"
#include "../interp.h"
#include "../object.h"
#include "../path.h"
#include "../type.h"

/*
for (superstitious pseudo-)optimization, i think there are 3 ways to deal with errors:
	1. error caught but stack trace not used for anything

		try:
			outer let value = parse_string_to_integer(user_input)
		catch ValueError:
			print("Please give a valid integer.")
			return

	2. error caught and stack trace needed

		try:
			download_file()
		catch HttpError e:
			write_stack_trace_to_file(e, log_file)
			return

	3. error never caught, so stack trace is displayed

ideally 1 should be fast, so this could be optimized by not copying the stack trace anywhere in that case
currently that's not implemented because it would be kinda complicated
*/

static void destroy_error(Object *obj, bool decrefrefs, bool freenonrefs)
{
	ErrObject *err = (ErrObject *)obj;
	if (decrefrefs)
		OBJECT_DECREF(err->msgstr);
	if (freenonrefs) {
		if (err->ownstack)
			free(err->stack);
	}
}


// nomemerr is not created with malloc() because ... you know

static StringObject nomemerr_string = STRINGOBJ_COMPILETIMECREATE(
	'n','o','t',' ','e','n','o','u','g','h',' ','m','e','m','o','r','y');
static ErrObject nomemerr = OBJECT_COMPILETIMECREATE(&errobj_type_nomem,
	.msgstr = &nomemerr_string,
	.stack = NULL,
	.stacklen = 0,
	.ownstack = false,
);

static ErrObject *compile_time_created_errors[] = { &nomemerr };


void errobj_set_obj(Interp *interp, ErrObject *err)
{
	if (err->ownstack)     // may happen if same error is thrown twice
		free(err->stack);

	err->stack = interp->stack.ptr;
	err->stacklen = interp->stack.len;
	err->ownstack = false;

	assert(!interp->err);
	interp->err = err;
	OBJECT_INCREF(err);
}

void errobj_set_nomem(Interp *interp)
{
	errobj_set_obj(interp, &nomemerr);
}


// error setting functions don't do error handling with different return values, because who
// cares if they fail to set the requested error and instead set NoMemError or something :D

static ErrObject *create_error_from_string(Interp *interp, const struct Type *errtype, StringObject *str)
{
	ErrObject *obj = object_new(interp, errtype, destroy_error, sizeof(*obj));
	if (!obj)     // refactoring note: MAKE SURE that errobj_set_nomem() doesn't recurse here
		return NULL;

	obj->msgstr = str;
	obj->stack = NULL;
	obj->stacklen = 0;
	obj->ownstack = false;
	OBJECT_INCREF(str);
	return obj;
}

static void set_from_string_obj(Interp *interp, const struct Type *errtype, StringObject *str)
{
	ErrObject *obj = create_error_from_string(interp, errtype, str);
	if (!obj)
		return;
	errobj_set_obj(interp, obj);
	OBJECT_DECREF(obj);
}

void errobj_set(Interp *interp, const struct Type *errtype, const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	StringObject *str = stringobj_new_vformat(interp, fmt, ap);
	va_end(ap);

	if (str) {
		set_from_string_obj(interp, errtype, str);
		OBJECT_DECREF(str);
	}
}

void errobj_set_oserr(Interp *interp, const char *fmt, ...)
{
	int savno = errno;

	va_list ap;
	va_start(ap, fmt);
	StringObject *str = stringobj_new_vformat(interp, fmt, ap);
	va_end(ap);
	if (!str)
		return;

	if (savno)
		errobj_set(interp, &errobj_type_os, "%S: %s (errno %d)", str, strerror(savno), savno);
	else
		set_from_string_obj(interp, &errobj_type_os, str);
	OBJECT_DECREF(str);
}


static bool tostring_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	StringObject *s = ((ErrObject *) args[0])->msgstr;
	OBJECT_INCREF(s);
	*result = (Object *)s;
	return true;
}
FUNCOBJ_COMPILETIMECREATE(tostring, &stringobj_type, { &errobj_type_error });

static FuncObject *methods[] = { &tostring };

static Object *error_string_constructor(Interp *interp, const struct Type *errtype, struct Object *const *args, size_t nargs)
{
	assert(nargs == 1);
	return (Object *) create_error_from_string(interp, errtype, (StringObject *) args[0]);
}


// if the ->stack of a compile-time created error is set, then this free()s it
static bool freeing_cb_added = false;
static void freeing_cb(void)
{
	for (size_t i = 0; i < sizeof(compile_time_created_errors)/sizeof(compile_time_created_errors[0]); i++)
	{
		assert(compile_time_created_errors[i]->refcount == 1);
		if (compile_time_created_errors[i]->ownstack)
			free(compile_time_created_errors[i]->stack);
	}
}

void errobj_beginhandling(Interp *interp, ErrObject *err)
{
	if (!freeing_cb_added) {
		// not much can be done if the atexit fails, other than try again later
		atexit(freeing_cb);
		freeing_cb_added = true;
	}

	// check that error has been thrown, and this function hasn't been called after the throw
	assert(err->stack == interp->stack.ptr);
	assert(!err->ownstack);

	err->ownstack = true;

	if (err->stacklen == 0)
		goto set_empty_stack;

	struct InterpStackItem *stackcp = malloc(sizeof(stackcp[0]) * err->stacklen);
	if (!stackcp)
		goto set_empty_stack;   // not ideal, but better than being unable to handle the error at all

	memcpy(stackcp, interp->stack.ptr, sizeof(stackcp[0]) * err->stacklen);
	err->stack = stackcp;
	return;

set_empty_stack:
	err->stack = NULL;
	err->stacklen = 0;
	err->ownstack = true;
}


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

void errobj_printstack(Interp *interp, ErrObject *err)
{
	fprintf(stderr, "asda error: ");   // TODO: include type name somehow

	// TODO: create a stringobj_toutf8 that doesn't do mallocs?
	const char *msg;
	size_t len;
	if (stringobj_toutf8(err->msgstr, &msg, &len)) {
		fwrite(msg, 1, len, stderr);
		fprintf(stderr, "\n");
	} else {
		assert(interp->err == &nomemerr);
		OBJECT_DECREF(interp->err);
		interp->err = NULL;
		fprintf(stderr, "(ran out of memory while trying to print error message)\n");
	}

	for (long i = (long)err->stacklen - 1; i >= 0; i--) {
		struct InterpStackItem it = err->stack[i];

		// TODO: figure out how to do this without symlink issues and ".."
		char *fullpath = path_concat_dotdot(interp->basedir, it.srcpath);

		const char *word = (i == (long)err->stacklen - 1) ? "in" : "by";
		if (fullpath)
			fprintf(stderr, "  %s file \"%s\"", word, fullpath);
		else
			fprintf(stderr, "  %s file \"%s\" (could not get full path)", word, it.srcpath);
		fprintf(stderr, ", line %zu\n    ", it.lineno);

		if (!print_source_line(fullpath, it.lineno))
			printf("(error while reading source file)\n");

		free(fullpath);
	}
}


#define BOILERPLATE(NAME, BASE, CONSTRUCTOR) \
	const struct Type NAME = TYPE_BASIC_COMPILETIMECREATE((BASE), (CONSTRUCTOR), methods, sizeof(methods)/sizeof(methods[0]))
BOILERPLATE(errobj_type_error, NULL, NULL);
BOILERPLATE(errobj_type_nomem, &errobj_type_error, NULL);
BOILERPLATE(errobj_type_variable, &errobj_type_error, error_string_constructor);
BOILERPLATE(errobj_type_value, &errobj_type_error, error_string_constructor);
BOILERPLATE(errobj_type_os, &errobj_type_error, error_string_constructor);
#undef BOILERPLATE
