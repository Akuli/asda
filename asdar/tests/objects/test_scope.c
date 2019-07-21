#include <assert.h>
#include <src/interp.h>
#include <src/object.h>
#include <src/objects/scope.h>
#include "../util.h"


TEST(scope_newsub_and_getforlevel)
{
	ScopeObject *a = scopeobj_newsub(interp, interp->builtinscope, 10);
	ScopeObject *b = scopeobj_newsub(interp, a, 10);
	ScopeObject *c = scopeobj_newsub(interp, b, 10);

	ScopeObject *shouldB[] = { interp->builtinscope, a, b, c };
	ScopeObject *is[4][4] = {
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
			ScopeObject *scope = is[level][i];
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
	ScopeObject *scope = scopeobj_newsub(interp, interp->builtinscope, 0);
	assert(scope);
	OBJECT_DECREF(scope);
}
