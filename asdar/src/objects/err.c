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
static StringObject nomemerr_string = STRINGOBJ_COMPILETIMECREATE(
	'n','o','t',' ','e','n','o','u','g','h',' ','m','e','m','o','r','y');
static ErrObject nomemerr = {
	.head = object_compiletime_head,
	.type = &errtype_nomem,
	.msgstr = &nomemerr_string,
};


#define ARRAY_COPY(DST, SRC, N) do{ \
	assert( sizeof((SRC)[0]) == sizeof((DST)[0]) ); \
	memcpy((DST), (SRC), (N)*sizeof((SRC)[0])); \
} while(0)

void errobj_set_obj(Interp *interp, ErrObject *err)
{
	struct InterpErrStackItem insi;

	size_t maxlen = sizeof(insi.callstack) / sizeof(insi.callstack[0]);
	assert(maxlen % 2 == 0);

	if (interp->callstack.len > maxlen) {
		insi.callstacklen = maxlen;
		insi.callstackskip = interp->callstack.len - maxlen;
		ARRAY_COPY(insi.callstack, interp->callstack.ptr, maxlen/2);
		ARRAY_COPY(insi.callstack + maxlen/2, interp->callstack.ptr + interp->callstack.len - maxlen/2, maxlen/2);
	} else {
		insi.callstacklen = interp->callstack.len;
		insi.callstackskip = 0;
		ARRAY_COPY(insi.callstack, interp->callstack.ptr, interp->callstack.len);
	}

	insi.errobj = err;
	OBJECT_INCREF(err);

	// error handling code must ensure that there's always room for one more error
	assert(interp->errstack.alloc >= interp->errstack.len + 1);
	dynarray_push_itwillfit(&interp->errstack, insi);
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

bool errobj_begintry(Interp *interp)
{
	/*
	There must be enough room for 2 errors, because we can have an error in try
	and then another error while handling that in 'catch'.

	FIXME: this should allocate room for more than 2 errors with nested trys
	*/
	return dynarray_alloc(interp, &interp->errstack, interp->errstack.len + 2);
}


void errobj_printstack(Interp *interp, ErrObject *err)
{
	assert(0);   // TODO
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
