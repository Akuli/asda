#ifndef GC_H
#define GC_H

// I don't fully understand why compiling fails without this
#include "objtyp.h"    // IWYU pragma: keep
struct Interp;
struct Object;

// this is the type of interp.gc
// think of the contents of this struct as an implementation detail
struct Gc {
	// the object list doesn't include statically allocated objects
	struct Object **objects;
	size_t objectslen;
	size_t objectssz;
};

// never fails
void gc_init(struct Gc *gc);
void gc_quit(struct Gc gc);

// returns false on error
bool gc_addobject(struct Interp *interp, struct Object *obj);
void gc_onrefcount0(struct Interp *interp, struct Object *obj);

#endif   // GC_H
