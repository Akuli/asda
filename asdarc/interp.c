#include "interp.h"
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>
#include "objects/scope.h"


bool interp_init(struct Interp *interp, const char *argv0)
{
	interp->argv0 = argv0;
	interp->errstr[0] = 0;

	if (!( interp->builtinscope = scopeobj_newglobal(interp) ))
		return false;
	return true;
}

void interp_destroy(struct Interp *interp)
{
	OBJECT_DECREF(interp->builtinscope);
}

void interp_errstr_printf_errno(struct Interp *interp, const char *fmt, ...)
{
	int errsav = errno;
	assert(interp->errstr[0] == 0);   // don't overwrite a previous error

#define where2print (interp->errstr + strlen(interp->errstr))
#define bytesleft ( (unsigned)(sizeof(interp->errstr) - strlen(interp->errstr)) )

	va_list ap;
	va_start(ap, fmt);
	if(bytesleft>1)
		vsnprintf(where2print, bytesleft, fmt, ap);
	va_end(ap);

	if(errsav && bytesleft>1)
		snprintf(where2print, bytesleft, " (errno %d: %s)", errsav, strerror(errsav));

#undef where2print
#undef bytesleft
}
