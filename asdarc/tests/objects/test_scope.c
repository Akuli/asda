#include <assert.h>
#include <src/objtyp.h>
#include <src/objects/scope.h>
#include "../util.h"


TEST(scope_newsub_and_getforlevel)
{
	Object *a = scopeobj_newsub(interp, interp->builtinscope, 10);
	Object *b = scopeobj_newsub(interp, a, 10);
	Object *c = scopeobj_newsub(interp, b, 10);

	Object *shouldB[] = { interp->builtinscope, a, b, c };
	Object *is[4][4] = {
		{
			scopeobj_getforlevel(interp->builtinscope, 0),
			scopeobj_getforlevel(a, 0),
			scopeobj_getforlevel(b, 0),
			scopeobj_getforlevel(c, 0),
		},
		{
			scopeobj_getforlevel(a, 1),
			scopeobj_getforlevel(b, 1),
			scopeobj_getforlevel(c, 1),
		},
		{
			scopeobj_getforlevel(b, 2),
			scopeobj_getforlevel(c, 2),
		},
		{
			scopeobj_getforlevel(c, 3),
		}
	};

	for (int level = 0; level < 4; level++) {
		for (int i = 0; i < 4-level; i++) {
			Object *scope = is[level][i];
			assert(scope);
			assert(scope == shouldB[level]);
		}
	}

	OBJECT_DECREF(a);
	OBJECT_DECREF(b);
	OBJECT_DECREF(c);
}

TEST(scope_0_locals)
{
	Object *scope = scopeobj_newsub(interp, interp->builtinscope, 0);
	assert(scope);
	OBJECT_DECREF(scope);
}
