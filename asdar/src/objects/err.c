#include "err.h"
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "string.h"
#include "../interp.h"
#include "../objtyp.h"


const struct Type errobj_type_error = { .methods = NULL, .nmethods = 0 };
const struct Type errobj_type_nomem = { .methods = NULL, .nmethods = 0 };
const struct Type errobj_type_variable = { .methods = NULL, .nmethods = 0 };
const struct Type errobj_type_value = { .methods = NULL, .nmethods = 0 };
const struct Type errobj_type_os = { .methods = NULL, .nmethods = 0 };

static void destroy_error(Object *obj, bool decrefrefs, bool freenonrefs)
{
	ErrObject *err = (ErrObject *)obj;
	if (decrefrefs)
		OBJECT_DECREF(err->msgstr);
}


// nomemerr is not created with malloc() because ... you know

static StringObject nomemerr_string = STRINGOBJ_COMPILETIMECREATE(
	'n','o','t',' ','e','n','o','u','g','h',' ','m','e','m','o','r','y');
static ErrObject nomemerr = OBJECT_COMPILETIMECREATE(&errobj_type_nomem,
	.msgstr = &nomemerr_string,
);


void errobj_set_nomem(Interp *interp)
{
	assert(!interp->err);
	interp->err = &nomemerr;
	OBJECT_INCREF(&nomemerr);
}


// error setting functions don't do error handling with different return values, because who
// cares if they fail to set the requested error and instead set NoMemError or something :D

static void set_from_string_obj(Interp *interp, const struct Type *errtype, StringObject *str)
{
	ErrObject *obj = object_new(interp, errtype, destroy_error, sizeof(*obj));
	if (!obj)     // refactoring note: MAKE SURE that errobj_set_nomem() doesn't recurse here
		return;

	obj->msgstr = str;
	OBJECT_INCREF(str);

	assert(!interp->err);
	interp->err = obj;
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
