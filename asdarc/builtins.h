#ifndef BUILTINS_H
#define BUILTINS_H

// I have no idea why iwyu wants to remove objtyp.h, even though this
// uses struct Object
#include <stddef.h>
#include "objtyp.h"   // IWYU pragma: keep

extern struct Object* const builtins[];
extern const size_t nbuiltins;


#endif   // BUILTINS_H
