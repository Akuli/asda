#include <assert.h>
#include <stdbool.h>
#include <stddef.h>
#include <src/interp.h>
#include <src/objtyp.h>
#include <src/objects/bool.h>
#include <src/objects/func.h>
#include "../util.h"

static unsigned int ncalls_ret, ncalls_noret;

char c_character = 'c';
struct ObjData leldata = {
	.val = &c_character,
	.destroy = NULL,
};

static bool compiletime_func_running;

#define BOILERPLATE_ARGS Interp *interp, struct ObjData data, Object *const *args, size_t nargs, Object **result
#define CHECK do{ \
	assert(interp); \
	assert(nargs == 2); \
	assert(args[0] == &boolobj_true); \
	assert(args[1] == &boolobj_false); \
	\
	if (compiletime_func_running) \
		assert(data.val == NULL); \
	else \
		assert(data.val == &c_character); \
	assert(data.destroy == NULL); \
} while(0)

static bool ret_cfunc(BOILERPLATE_ARGS) { CHECK; ncalls_ret++; *result = boolobj_c2asda(true); return true; }
static bool noret_cfunc(BOILERPLATE_ARGS) { CHECK; ncalls_noret++; *result = NULL; return true; }

struct FuncObjData compiletime_ret_data   = FUNCOBJDATA_COMPILETIMECREATE(ret_cfunc);
struct FuncObjData compiletime_noret_data = FUNCOBJDATA_COMPILETIMECREATE(noret_cfunc);
Object compiletime_ret   = OBJECT_COMPILETIMECREATE(&funcobj_type,   &compiletime_ret_data  );
Object compiletime_noret = OBJECT_COMPILETIMECREATE(&funcobj_type, &compiletime_noret_data);

static void check_calling(Interp *interp, Object *retf, Object *noretf)
{
	ncalls_ret = 0;
	Object *result;
	assert(funcobj_call(interp, retf, (Object*[]){ &boolobj_true, &boolobj_false }, 2, &result) == true);
	assert(ncalls_ret == 1);
	assert(result == &boolobj_true);
	OBJECT_DECREF(result);

	ncalls_noret = 0;
	Object *result2;
	bool bres = funcobj_call(interp, noretf, (Object*[]){ &boolobj_true, &boolobj_false }, 2, &result2);
	assert(result2 == NULL);
	assert(ncalls_noret == 1);
	assert(bres);
}


TEST(funcobj_compiletimecreate)
{
	compiletime_func_running = true;
	check_calling(interp, &compiletime_ret, &compiletime_noret);
}

TEST(funcobj_new)
{
	Object *ret = funcobj_new(interp, ret_cfunc, leldata);
	Object *noret = funcobj_new(interp, noret_cfunc, leldata);
	assert(ret);
	assert(noret);

	compiletime_func_running = false;
	check_calling(interp, ret, noret);

	OBJECT_DECREF(ret);
	OBJECT_DECREF(noret);
}
