#ifndef OBJECTS_FUNC_H
#define OBJECTS_FUNC_H

#include <stdbool.h>
#include <stddef.h>
#include "../interp.h"
#include "../objtyp.h"

extern const struct Type funcobj_type;

// returning functions set *result to their return value on success
// non-returning functions set it to NULL on success
// on failure, everything returns false and doesn't need to set *result
typedef bool (*funcobj_cfunc)(Interp*, struct ObjData userdata, Object *const *args, size_t nargs, Object **result);

// it is an implementation detail that this is here, don't rely on it
// currently it is needed for FUNCOBJDATA_COMPILETIMECREATE macros
struct FuncObjData {
	funcobj_cfunc cfunc;
	struct ObjData userdata;   // for passing data to cfunc
};

#define FUNCOBJDATA_COMPILETIMECREATE(f) { .cfunc = f }

/* Create a new FuncObj
 * userdata is destroyed on FuncObj destruction or on creation error
 * cfunc must set *result to NULL if it does not return anything.
 */
Object *funcobj_new(Interp *interp, funcobj_cfunc cfunc, struct ObjData userdata);

/** Call a FuncObj
 * Returns a boolean indicating success.
 * On success, sets `*result` to the return value of the function, or NULL if it didn't return a value.
 */
bool funcobj_call(Interp*, Object*, Object *const *args, size_t nargs, Object **result);

#endif // OBJECTS_FUNC_H
