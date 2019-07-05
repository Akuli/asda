#ifndef IMPORT_H
#define IMPORT_H

#include "interp.h"
#include <stdbool.h>


// the path should be relative to interp->basedir
// the module can be accessed with module.h functions after importing
// asserts that the module hasn't been imported earlier
bool import(Interp *interp, const char *path);


#endif  // IMPORT_H
