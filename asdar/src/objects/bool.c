#include "bool.h"
#include <stdbool.h>
#include <stddef.h>
#include "../object.h"

BoolObject boolobj_true = { .head = OBJECT_COMPILETIME_HEAD };
BoolObject boolobj_false = { .head = OBJECT_COMPILETIME_HEAD };

// https://stackoverflow.com/a/18636323
extern inline BoolObject *boolobj_c2asda(bool cbool);
extern inline bool boolobj_asda2c(BoolObject *asdabool);


// TODO: implement these completely in the compiler, similarly 'and', 'or'
static Object *not_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda(!boolobj_asda2c((BoolObject *) args[0]));
}

static Object *eq_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda(args[0] == args[1]);
}

const struct CFunc boolobj_cfuncs[] = {
	{ "not", 1, true, { .ret = not_cfunc }},
	{ "Bool==Bool", 2, true, { .ret = eq_cfunc }},
	{0},
};
