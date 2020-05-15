#include "builtin.h"
#include <stdbool.h>
#include <stdio.h>
#include "interp.h"
#include "object.h"
#include "objects/array.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/int.h"
#include "objects/string.h"


static bool print_func(Interp *interp, Object *const *args)
{
	StringObject *sobj = (StringObject*)args[0];
	const char *utf8 = stringobj_getutf8(sobj);

	if (fwrite(utf8, 1, sobj->utf8len, stdout) != sobj->utf8len
		|| putchar('\n') == EOF)
	{
		errobj_set_oserr(interp, "cannot write to stdout");
		return false;
	};
	return true;
}

static Object *not_func(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda(!boolobj_asda2c((BoolObject *) args[0]));
}

static Object *str_plus_str_func(Interp *interp, Object *const *args)
{
	return (Object *) stringobj_join(interp, (StringObject *const *) args, 2);
}

static Object *int_plus_int_func(Interp *interp, Object *const *args)
{
	return (Object *) intobj_add(interp, (IntObject *) args[0], (IntObject *) args[1]);
}

static Object *int_minus_int_func(Interp *interp, Object *const *args)
{
	return (Object *) intobj_sub(interp, (IntObject *) args[0], (IntObject *) args[1]);
}

static Object *int_times_int_func(Interp *interp, Object *const *args)
{
	return (Object *) intobj_mul(interp, (IntObject *) args[0], (IntObject *) args[1]);
}

static Object *minus_int_func(Interp *interp, Object *const *args)
{
	return (Object *) intobj_neg(interp, (IntObject *) args[0]);
}

static Object *int_eq_int_func(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda( intobj_cmp((IntObject *) args[0], (IntObject *) args[1])==0 );
}

static Object *str_eq_str_func(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda(stringobj_eq((StringObject *) args[0], (StringObject *) args[1]));
}

static Object *bool_eq_bool_func(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda( boolobj_asda2c((BoolObject *) args[0]) == boolobj_asda2c((BoolObject *) args[1]) );
}


#define RET(f, n)   { .ret = true,  { .ret   = (f) }, .nargs = (n) }
#define NORET(f, n) { .ret = false, { .noret = (f) }, .nargs = (n) }

const struct BuiltinFunc builtin_funcs[] = {
	NORET(print_func, 1),
	RET(not_func, 1),
	RET(str_plus_str_func, 2),
	RET(int_plus_int_func, 2),
	RET(int_minus_int_func, 2),
	RET(int_times_int_func, 2),
	RET(minus_int_func, 1),
	RET(int_eq_int_func, 2),
	RET(str_eq_str_func, 2),
	RET(bool_eq_bool_func, 2),
};
const size_t builtin_nfuncs = sizeof(builtin_funcs) / sizeof(builtin_funcs[0]);
