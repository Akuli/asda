#ifndef OBJECTS_FUNC_H
#define OBJECTS_FUNC_H

#include <stdbool.h>
#include <stddef.h>
#include "../interp.h"
#include "../objtyp.h"

extern const struct Type funcobj_type_ret;
extern const struct Type funcobj_type_noret;

typedef struct Object* (*funcobj_cfunc_ret  )(struct Interp *interp, struct ObjData data, struct Object **args, size_t nargs);
typedef bool           (*funcobj_cfunc_noret)(struct Interp *interp, struct ObjData data, struct Object **args, size_t nargs);

// it is an implementation detail that this is here, don't rely on it
// currently it is needed for FUNCOBJDATA_COMPILETIMECREATE macros
//
// this is also wrapped in a struct to make it a valid void* pointer value
struct FuncObjData {
	union {
		funcobj_cfunc_ret ret;
		funcobj_cfunc_noret noret;
	} cfunc;

	// for passing data to cfunc
	struct ObjData data;

	// these are added to the beginning of the arg list when calling the function
	struct Object **partial;
	size_t npartial;
};

// everything else defaults to NULL or 0
#define FUNCOBJDATA_COMPILETIMECREATE_NORET(f) { .cfunc = {.noret=(f)} }
#define FUNCOBJDATA_COMPILETIMECREATE_RET(  f) { .cfunc = {.ret  =(f)} }

// data is always destroyed (on error immediately, on success whenever function is destroyed)
struct Object *funcobj_new_noret(struct Interp *interp, funcobj_cfunc_noret f, struct ObjData data);
struct Object *funcobj_new_ret  (struct Interp *interp, funcobj_cfunc_ret   f, struct ObjData data);

struct Object *funcobj_new_partial(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs);

bool           funcobj_call_noret(struct Interp *interp, struct Object *f, struct Object **args, size_t nargs);
struct Object* funcobj_call_ret  (struct Interp *interp, struct Object *f, struct Object **args, size_t nargs);


#endif   // OBJECTS_FUNC_H
