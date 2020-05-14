// utilities for working with path strings
#ifndef PATH_H
#define PATH_H

#include <stdbool.h>
#include <stddef.h>

#if defined(_WIN32) || defined(_WIN64)
#define PATH_SLASH '\\'
#define PATH_SLASHSTR "\\"
#else
#define PATH_SLASH '/'
#define PATH_SLASHSTR "/"
#endif

enum PathConcatFlags {
	// Handle paths starting with ".." components and do funny stuff with symlinks.
	PATH_RMDOTDOT = 1 << 0,
};

// return current working directory as a \0-terminated string that must be free()'d
// sets errno and returns NULL on error
// if this runs out of mem, errno is set to ENOMEM and NULL is returned
// ENOMEM is not in C99, but windows and posix have it
char *path_getcwd(void);

// check if a path is absolute
// example: on non-Windows, /home/akuli/ö/src is absolute and ö/src is not
bool path_isabsolute(const char *path);

// return a copy of path if it's absolute, otherwise path joined with current working directory
// return value must be free()'d
// returns NULL and sets errno on error (ENOMEM if malloc() fails)
char *path_toabsolute(const char *path);

// join a NULL-terminated array of paths by PATH_SLASH
// sets errno to ENOMEM and returns NULL on no mem
// return value must be free()'d
char *path_concat(const char *const *paths, enum PathConcatFlags flags);

// on non-windows, path_findlastslash("a/b/c.ö) returns the index of "/" before "c"
// on windows, same gibberish with backslashes
// useful for separating dirnames and basenames
size_t path_findlastslash(const char *path);

// Is a newer than b? Returns 1 for newer, 0 for older or equally old, -1 for error.
int path_isnewerthan(const char *a, const char *b);

#endif    // PATH_H
