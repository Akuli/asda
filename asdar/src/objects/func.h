#ifndef OBJECTS_FUNC_H
#define OBJECTS_FUNC_H

#include <stdbool.h>
#include <stddef.h>
#include "../interp.h"
#include "../object.h"
#include "../type.h"

// returning functions set *result to their return value on success
// non-returning functions set it to NULL on success
// on failure, everything returns false and doesn't need to set *result
typedef bool (*funcobj_cfunc)(Interp*, struct ObjData userdata,
	Object *const *args, size_t nargs, Object **result);

typedef struct FuncObject {
	OBJECT_HEAD
	funcobj_cfunc cfunc;
	struct ObjData userdata;   // for passing data to cfunc
} FuncObject;

/*
usage:

	static bool lol_cfunc(Interp *interp, struct ObjData userdata, Object *const *args, size_t nargs, Object **result)
	{
		...
	}

	FUNCOBJ_COMPILETIMECREATE(lol, lol_cfunc, &intobj_type, { &intobj_type });

the "..." is argument types, in braces
currently it is not possible to compiletimecreate a function that takes 0 args :(
*/
#define FUNCOBJ_COMPILETIMECREATE(NAME, CFUNC, RETTYPE, ...) \
	TYPE_FUNC_COMPILETIMECREATE(NAME##_type, RETTYPE, __VA_ARGS__); \
	static FuncObject NAME = OBJECT_COMPILETIMECREATE((const struct Type *) &NAME##_type, .cfunc = (CFUNC))

/* Create a new FuncObj
 * userdata is destroyed on FuncObj destruction or on creation error
 * cfunc must set *result to NULL if it does not return anything.
 */
FuncObject *funcobj_new(Interp *interp, const struct TypeFunc *type, funcobj_cfunc cfunc, struct ObjData userdata);

/** Call a FuncObj
 * Returns a boolean indicating success.
 * On success, sets `*result` to the return value of the function, or NULL if it didn't return a value.
 */
bool funcobj_call(Interp *interp, FuncObject *f,
	Object *const *args, size_t nargs, Object **result);

#endif // OBJECTS_FUNC_H
