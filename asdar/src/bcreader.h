// bytecode reader

#ifndef BCREADER_H
#define BCREADER_H

#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include "interp.h"



// bcpathrel must be relative to interp->basedir, it's always freed
bool bcreader_read(Interp *interp, char *bcpathrel);


#endif   // BCREADER_H
