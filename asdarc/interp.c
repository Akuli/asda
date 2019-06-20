#include "interp.h"
#include <assert.h>
#include <errno.h>
#include <stdarg.h>
#include <stdio.h>
#include <string.h>
#include <stdbool.h>


bool interp_init(struct Interp *interp, const char *argv0)
{
	interp->argv0 = argv0;
	return true;
}

void interp_destroy(struct Interp *interp)
{
}

void interp_errstr_printf_errno(struct Interp *interp, const char *fmt, ...)
{
	int saverrno = errno;

	assert(interp->errstr[0] == 0);   // don't overwrite a previous error
	char *ptr = interp->errstr;
	char *end = interp->errstr + (sizeof(interp->errstr)-1);
	int n;

	if( ptr < end && (n = snprintf(ptr, (unsigned)(end-ptr), "%.20s: ", interp->argv0)) > 0 )
		ptr += n;

	va_list ap;
	va_start(ap, fmt);
	if( ptr < end && (n = vsnprintf(ptr, (unsigned)(end-ptr), fmt, ap)) > 0 )
		ptr += n;
	va_end(ap);

	if(saverrno && ptr < end && (n = snprintf(ptr, (unsigned)(end-ptr), " (errno %d: %s)", saverrno, strerror(saverrno))) > 0 )
		ptr += n;

	assert(ptr <= end);
	*ptr = 0;
}
