#ifndef RUN_H
#define RUN_H

#include <stdbool.h>
#include <stddef.h>
#include "interp.h"

bool run_module(Interp *interp, const struct InterpModInfo *mod);


#endif   // RUN_H
