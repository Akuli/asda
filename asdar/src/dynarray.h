#ifndef DYNARRAY_H
#define DYNARRAY_H

#include <assert.h>   // IWYU pragma: keep
#include <stdbool.h>
#include <string.h>   // IWYU pragma: keep

// don't access alloc outside this file and dynarray.c
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
after a successful dynarray_alloc(&da, N), you can put N items to the dynamic array without allocating more
i.e. dynarray_push will always succeed and 'da.ptr[da.len++] = item' is also valid
dynarray_alloc returns a success bool
*/
#define dynarray_alloc(DAP, N) dynarray_alloc_internal((void**) &(DAP)->ptr, &(DAP)->alloc, sizeof((DAP)->ptr[0]), (N))

// returns a success bool
#define dynarray_push(DAP, OBJ) ( \
	dynarray_alloc((DAP), (DAP)->len + 1) && \
	( ((DAP)->ptr[(DAP)->len++] = (OBJ)) , true ) \
)

// more efficient than a push in a loop
// returns a success bool
#define dynarray_pushmany(DAP, OBJS, N) ( \
	dynarray_alloc((DAP), (DAP)->len + (N)) && \
	( memcpy((DAP)->ptr + (DAP)->len, (OBJS), (N) * sizeof((DAP)->ptr[0])) , true ) && \
	( ((DAP)->len += (N)) , true ) \
)

// bad things happen if the dynarray is empty, never fails otherwise
#define dynarray_pop(DAP) ( (DAP)->ptr[--(DAP)->len] )

// you can use it after filling a DynArray to free up not-needed memory
#define dynarray_shrink2fit(DAP) do { \
	(DAP)->ptr = realloc( (DAP)->ptr, sizeof((DAP)->ptr[0]) * (DAP)->alloc ); \
	if(( (DAP)->alloc = (DAP)->len )) { \
		/* this should never allocate more, so it doesn't make sense for it to fail */ \
		assert((DAP)->ptr); \
	} else { \
		/* for consistency and because why not */ \
		(DAP)->ptr = NULL; \
	} \
} while(0)

// like the name says, don't use this outside this h file and the related c file
bool dynarray_alloc_internal(void **ptr, size_t *alloc, size_t itemsz, size_t enough);

#endif    // DYNARRAY_H
