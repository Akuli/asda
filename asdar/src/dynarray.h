#ifndef DYNARRAY_H
#define DYNARRAY_H

// this file is not IWYU'd (see Makefile) because it does too much magic for iwyu to understand
#include <assert.h>
#include <stdbool.h>
#include <string.h>


#define DynArray(T) struct { \
	T *ptr;       /* the items, free this when you are done with the dynarray */ \
	size_t len;   /* number of items */ \
	size_t alloc; /* meant to be used only in dynarray.c */ \
}

// in the rest of this file, DAP is a pointer to a DynArray

/* example:

	DynArray(int) da;
	dynarray_init(&da);
	...
	free(da.ptr);
*/
#define dynarray_init(DAP) do { \
	(DAP)->ptr = NULL; \
	(DAP)->len = 0; \
	(DAP)->alloc = 0; \
} while(0)

/*
after a successful dynarray_alloc(&da, N), da can hold N items without allocating more
i.e. dynarray_push will always succeed and 'da.ptr[da.len++] = item' is also valid
dynarray_alloc returns a success bool
*/
#define dynarray_alloc(INTERP, DAP, N) \
	dynarray_alloc_internal((INTERP), (void**) &(DAP)->ptr, &(DAP)->alloc, sizeof((DAP)->ptr[0]), (N))

// returns a success bool
#define dynarray_push(INTERP, DAP, OBJ) ( \
	dynarray_alloc((INTERP), (DAP), (DAP)->len + 1) && \
	( ((DAP)->ptr[(DAP)->len++] = (OBJ)) , true ) \
)

// you can use this instead of dynarray_push when you know that there is room in the dynarray
// this returns nothing
#define dynarray_push_itwillfit(DAP, OBJ) do { \
	(DAP)->ptr[(DAP)->len++] = (OBJ); \
} while(0)

/*
bad things happen if the dynarray is empty, never fails otherwise
to ignore popped value and avoid compiler warning:

	(void) dynarray_pop(&da);
*/
#define dynarray_pop(DAP) ( (DAP)->ptr[--(DAP)->len] )

// you can use it after filling a DynArray to free up not-needed memory
#define dynarray_shrink2fit(DAP) do { \
	(DAP)->ptr = realloc( (DAP)->ptr, sizeof((DAP)->ptr[0]) * (DAP)->len ); \
	if(( (DAP)->alloc = (DAP)->len )) { \
		/* this should never allocate more, so it doesn't make sense for it to fail */ \
		assert((DAP)->ptr); \
	} else { \
		/* for consistency and because why not */ \
		free((DAP)->ptr);     /* needed for valgrinding cleanly */ \
		(DAP)->ptr = NULL; \
	} \
} while(0)

// forward declare because interp.h includes this file
struct Interp;

// like the name says, don't use this outside this h file and the related c file
bool dynarray_alloc_internal(struct Interp *interp, void **ptr, size_t *alloc, size_t itemsz, size_t enough);

#endif    // DYNARRAY_H
