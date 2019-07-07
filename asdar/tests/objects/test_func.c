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

#define BOILERPLATE_ARGS Interp *interp, struct ObjData data, Object *const *args, size_t nargs
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

static Object *ret_cfunc(BOILERPLATE_ARGS) { CHECK; ncalls_ret++; return boolobj_c2asda(true); }
static bool noret_cfunc(BOILERPLATE_ARGS) { CHECK; ncalls_noret++; return true; }

struct FuncObjData compiletime_ret_data   = FUNCOBJDATA_COMPILETIMECREATE_RET  (ret_cfunc  );
struct FuncObjData compiletime_noret_data = FUNCOBJDATA_COMPILETIMECREATE_NORET(noret_cfunc);
Object compiletime_ret   = OBJECT_COMPILETIMECREATE(&funcobj_type_ret,   &compiletime_ret_data  );
Object compiletime_noret = OBJECT_COMPILETIMECREATE(&funcobj_type_noret, &compiletime_noret_data);

static void check_calling(Interp *interp, Object *retf, Object *noretf)
{
	ncalls_ret = 0;
	Object *ores = funcobj_call_ret  (interp, retf, (Object*[]){ &boolobj_true, &boolobj_false }, 2);
	assert(ncalls_ret == 1);
	assert(ores == &boolobj_true);
	OBJECT_DECREF(ores);

	ncalls_noret = 0;
	bool bres = funcobj_call_noret(interp, noretf, (Object*[]){ &boolobj_true, &boolobj_false }, 2);
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
	Object *ret = funcobj_new_ret(interp, ret_cfunc, leldata);
	Object *noret = funcobj_new_noret(interp, noret_cfunc, leldata);
	assert(ret);
	assert(noret);

	compiletime_func_running = false;
	check_calling(interp, ret, noret);

	OBJECT_DECREF(ret);
	OBJECT_DECREF(noret);
}
