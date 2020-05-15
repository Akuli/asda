#include "err.h"
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "string.h"
#include "../interp.h"
#include "../object.h"


static void destroy_error(Object *obj, bool decrefrefs, bool freenonrefs)
{
	ErrObject *err = (ErrObject *)obj;
	if (decrefrefs)
		OBJECT_DECREF(err->msgstr);
}


// nomemerr is not created with malloc() because ... you know
static StringObject nomemerr_string = STRINGOBJ_COMPILETIMECREATE("not enough memory");
static ErrObject nomemerr = {
	.head = OBJECT_COMPILETIME_HEAD,
	.type = &errtype_nomem,
	.msgstr = &nomemerr_string,
};


void errobj_set_obj(Interp *interp, ErrObject *err)
{
	assert(err);
	assert(!interp->err);   // run.c should handle this
	interp->err = err;
	OBJECT_INCREF(err);
}

void errobj_set_nomem(Interp *interp)
{
	errobj_set_obj(interp, &nomemerr);
}


// error setting functions don't do error handling with different return values, because who
// cares if they fail to set the requested error and instead set NoMemError or something :D

static ErrObject *create_error_from_string(Interp *interp, const struct ErrType *et, StringObject *str)
{
	ErrObject *obj = object_new(interp, destroy_error, sizeof(*obj));
	if (!obj)     // refactoring note: MAKE SURE that errobj_set_nomem() doesn't recurse here
		return NULL;

	obj->msgstr = str;
	OBJECT_INCREF(str);
	obj->type = et;
	return obj;
}

static void set_from_string_obj(Interp *interp, const struct ErrType *errtype, StringObject *str)
{
	ErrObject *obj = create_error_from_string(interp, errtype, str);
	if (!obj)
		return;
	errobj_set_obj(interp, obj);
	OBJECT_DECREF(obj);
}

void errobj_set(Interp *interp, const struct ErrType *errtype, const char *fmt, ...)
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
	if (errno == ENOMEM) {
		// message and stuff ignored to avoid allocations
		errobj_set_nomem(interp);
		return;
	}

	int savno = errno;

	va_list ap;
	va_start(ap, fmt);
	StringObject *str = stringobj_new_vformat(interp, fmt, ap);
	va_end(ap);
	if (!str)
		return;

	if (savno)
		errobj_set(interp, &errtype_os, "%S: %s (errno %d)", str, strerror(savno), savno);
	else
		set_from_string_obj(interp, &errtype_os, str);
	OBJECT_DECREF(str);
}


static Object *error_string_constructor(Interp *interp, const struct ErrType *errtype, struct Object *const *args, size_t nargs)
{
	assert(nargs == 1);
	return (Object *) create_error_from_string(interp, errtype, (StringObject *) args[0]);
}

static bool tostring_cfunc(Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result)
{
	StringObject *s = ((ErrObject *) args[0])->msgstr;
	OBJECT_INCREF(s);
	*result = (Object *)s;
	return true;
}
/*FUNCOBJ_COMPILETIMECREATE(tostring, &stringobj_type, { &errtype_error });

static struct TypeAttr attrs[] = {
	{ TYPE_ATTR_METHOD, &tostring },
};
*/

const struct ErrType errtype_nomem = { "NoMemError" };
const struct ErrType errtype_variable = { "VariableError" };
const struct ErrType errtype_value = { "ValueError" };
const struct ErrType errtype_os = { "OsError" };
