#ifndef IMPORT_H
#define IMPORT_H

#include "interp.h"
#include <stdbool.h>


// the path should be relative to interp->basedir, and is always free()d
bool import(Interp *interp, char *path);


#endif  // IMPORT_H
