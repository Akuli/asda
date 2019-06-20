#ifndef INTERP_H
#define INTERP_H

#include <stdbool.h>

struct Interp {
	const char *argv0;

	// DON'T SPRINTF ARBITRARY STRINGS HERE
	// TODO: add exceptions to asda
	char errstr[200];
};

// returns false on no mem
bool interp_init(struct Interp *interp, const char *argv0);

// never fails
void interp_destroy(struct Interp *interp);

// you can print arbitrarily long strings with this, uses snprintf internally
void interp_errstr_printf_errno(struct Interp *interp, const char *fmt, ...);

#endif   // INTERP_H
