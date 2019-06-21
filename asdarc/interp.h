#ifndef INTERP_H
#define INTERP_H

#include <errno.h>   // IWYU pragma: keep
#include <stdbool.h>
#include "objtyp.h"

struct Interp {
	const char *argv0;
	struct Object *builtinscope;

	// DON'T PUT ARBITRARILY LONG STRINGS HERE
	// TODO: add exceptions to asda
	char errstr[200];
};

// returns false and sets an error to interp->errstr on no mem
bool interp_init(struct Interp *interp, const char *argv0);

// never fails
void interp_destroy(struct Interp *interp);

// you can print arbitrarily long strings with these, uses snprintf internally
void interp_errstr_printf_errno(struct Interp *interp, const char *fmt, ...);
#define interp_errstr_printf(...) do{ \
	errno = 0; \
	interp_errstr_printf_errno(__VA_ARGS__); \
}while(false)
#define interp_errstr_nomem(interp) interp_errstr_printf((interp), "not enough memory");

#endif   // INTERP_H
