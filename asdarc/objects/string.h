#ifndef OBJECTS_STRING_H
#define OBJECTS_STRING_H

#include <stdbool.h>
#include <stddef.h>
#include <stdint.h>
#include "../interp.h"
#include "../objtyp.h"

struct Object *stringobj_new(struct Interp *interp, const uint32_t *val, size_t len);

/*
the val will be freed (if error then immediately, otherwise whenever the
object is destroyed)
*/
struct Object *stringobj_new_nocpy(struct Interp *interp, uint32_t *val, size_t len);

struct Object *stringobj_new_utf8(struct Interp *interp, const char *utf, size_t utflen);

/*
behaves like utf8_encode

note: you need to change this to take an interp as argument if if you add
strings that have interp==NULL (i.e. strings created at compile time)
*/
bool stringobj_toutf8(struct Object *obj, char **val, size_t *len);

extern const struct Type stringobj_type;

#endif   // OBJECTS_STRING_H
