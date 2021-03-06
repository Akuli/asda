#include <stdbool.h>
#include <stdlib.h>
#include "dynarray.h"
#include "interp.h"
#include "objects/err.h"

#define max(a, b) ( (a)>(b) ? (a) : (b) )
#define max3(a, b, c) max(a, max(b, c))

bool dynarray_alloc_internal(Interp *interp, void **ptr, size_t *alloc, size_t itemsz, size_t enough)
{
	if (*alloc >= enough)
		return true;

	size_t newalloc = max3(2*(*alloc), enough, 4);
	void *tmp = realloc(*ptr, newalloc * itemsz);
	if (!tmp) {
		errobj_set_nomem(interp);
		return false;
	}

	*alloc = newalloc;
	*ptr = tmp;
	return true;
}
