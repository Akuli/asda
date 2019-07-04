#ifndef INTERP_H
#define INTERP_H

// errno is used in the macros, iwyu doesn't know that
#include <errno.h>   // IWYU pragma: keep
#include <stdbool.h>

// forward declarations needed because many things need an Interp
struct ObjectStruct;
struct Module;

typedef struct InterpStruct {
	const char *argv0;
	struct ObjectStruct *builtinscope;

	// the only object created at runtime that has ->prev == NULL
	// all (not yet destroyed) runtime created objects can be found from here with ->next
	struct ObjectStruct *objliststart;

	// DON'T PUT ARBITRARILY LONG STRINGS HERE
	// TODO: add exceptions to asda
	char errstr[200];

	// don't access this directly, use functions in module.h instead
	struct Module *firstmod;
} Interp;

// returns false and sets an error to interp->errstr on no mem
bool interp_init(Interp *interp, const char *argv0);

// never fails, always leaves errstr untouched
void interp_destroy(Interp *interp);

// you can print arbitrarily long strings with these, uses snprintf internally
void interp_errstr_printf_errno(Interp *interp, const char *fmt, ...);
#define interp_errstr_printf(...) do{ \
	errno = 0; \
	interp_errstr_printf_errno(__VA_ARGS__); \
}while(false)
#define interp_errstr_nomem(interp) interp_errstr_printf((interp), "not enough memory")

#endif   // INTERP_H
