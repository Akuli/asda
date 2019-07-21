#ifndef BUILTINS_H
#define BUILTINS_H

// I have no idea why iwyu wants to remove object.h, even though this
// uses Object
#include <stddef.h>
#include "object.h"   // IWYU pragma: keep

extern Object* const builtin_objects[];
extern const size_t builtin_nobjects;

extern const struct Type* const builtin_types[];
extern const size_t builtin_ntypes;


#endif   // BUILTINS_H
