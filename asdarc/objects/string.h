#ifndef OBJECTS_STRING_H
#define OBJECTS_STRING_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "../interp.h"
#include "../objtyp.h"

Object *stringobj_new(Interp *interp, const uint32_t *val, size_t len);

/*
the val will be freed (if error then immediately, otherwise whenever the
object is destroyed)
*/
Object *stringobj_new_nocpy(Interp *interp, uint32_t *val, size_t len);

Object *stringobj_new_utf8(Interp *interp, const char *utf, size_t utflen);

/*
behaves like utf8_encode
DON'T FREE the val

note: you need to change this to take an interp as argument if if you add
strings that have interp==NULL (i.e. strings created at compile time)
*/
bool stringobj_toutf8(Object *obj, const char **val, size_t *len);

// joins all da strings
Object *stringobj_join(Interp *interp, Object *const *strs, size_t nstrs);

extern const struct Type stringobj_type;

#endif   // OBJECTS_STRING_H
