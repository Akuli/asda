#ifndef RUNNER_H
#define RUNNER_H

#include <stdbool.h>
#include <stddef.h>
#include "dynarray.h"
#include "code.h"
#include "interp.h"
#include "object.h"

bool runner_run(Interp *interp, size_t startidx);


#endif   // RUNNER_H
