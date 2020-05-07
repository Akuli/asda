#ifndef run_H
#define run_H

#include <stdbool.h>
#include <stddef.h>
#include "dynarray.h"
#include "code.h"
#include "interp.h"
#include "object.h"

bool run(Interp *interp, size_t startidx);


#endif   // run_H
