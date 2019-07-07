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

struct ErrData {
	Object *msgstr;
	// TODO: stack trace info
	// TODO: chained errors
	//       but maybe not as linked list?
	//       if linked list then how about multiple NoMemErrors chaining? avoid chaining onto itself
};

static void errdata_destructor(void *vp, bool decrefrefs, bool freenonrefs)
{
	struct ErrData *ed = vp;
	if (decrefrefs)
		OBJECT_DECREF(ed->msgstr);
	if (freenonrefs)
		free(ed);
}


// nomemerr is not created with malloc() because ... you know

static struct StringObjData nomemerr_string_data = STRINGOBJDATA_COMPILETIMECREATE(
	'n','o','t',' ','e','n','o','u','g','h',' ','m','e','m','o','r','y');
static Object nomemerr_string = OBJECT_COMPILETIMECREATE(&stringobj_type, &nomemerr_string_data);
static struct ErrData nomemerr_data = { .msgstr = &nomemerr_string };
static Object nomemerr = OBJECT_COMPILETIMECREATE(&errobj_type_nomem, &nomemerr_data);


void errobj_set_nomem(Interp *interp)
{
	assert(!interp->err);
	interp->err = &nomemerr;
	OBJECT_INCREF(&nomemerr);
}


// error setting functions don't do error handling with different return values, because who
// cares if they fail to set the requested error and instead set NoMemError or something :D

static void set_from_string_obj(Interp *interp, const struct Type *errtype, Object *str)
{
	struct ErrData *ed = malloc(sizeof(*ed));
	if (!ed) {
		// refactoring note: MAKE SURE that errobj_set_nomem() doesn't recurse here
		errobj_set_nomem(interp);
		return;
	}

	ed->msgstr = str;
	OBJECT_INCREF(str);

	Object *obj = object_new(interp, errtype, (struct ObjData){
		.val = ed,
		.destroy = errdata_destructor,
	});
	if (!obj)
		return;

	assert(!interp->err);
	interp->err = obj;
}

void errobj_set(Interp *interp, const struct Type *errtype, const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	Object *str = stringobj_new_vformat(interp, fmt, ap);
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
	Object *str = stringobj_new_vformat(interp, fmt, ap);
	va_end(ap);
	if (!str)
		return;

	if (savno)
		errobj_set(interp, &errobj_type_os, "%S: %s (errno %d)", str, strerror(savno), savno);
	else
		set_from_string_obj(interp, &errobj_type_os, str);
	OBJECT_DECREF(str);
}

Object *errobj_getstring(Object *err)
{
	struct ErrData *ed = err->data.val;
	OBJECT_INCREF(ed->msgstr);
	return ed->msgstr;
}
