// utilities for working with path strings
#ifndef PATH_H
#define PATH_H

#ifdef __cplusplus
extern "C" {
#else
#define noexcept
#endif

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
	// If possible, remove ".." components without doing funny stuff with symlinks.
	PATH_RMDOTDOT = 1 << 0,

	// Always remove ".." components, but do funny stuff with symlinks when the
	// path doesn't exist.
	PATH_RMDOTDOT_DUMB = 1 << 1,

	// Use the parent of the fistr path instead of the first path
	PATH_FIRSTPARENT = 1 << 2,
};

// return current working directory as a \0-terminated string that must be free()'d
// sets errno and returns NULL on error
// if this runs out of mem, errno is set to ENOMEM and NULL is returned
// ENOMEM is not in C99, but windows and posix have it
char *path_getcwd(void) noexcept;

// check if a path is absolute
// example: on non-Windows, /home/akuli/ö/src is absolute and ö/src is not
bool path_isabsolute(const char *path) noexcept;

// join a NULL-terminated array of paths by PATH_SLASH
// sets errno to ENOMEM and returns NULL on no mem
// return value must be free()'d
char *path_concat(const char *const *paths, enum PathConcatFlags flags) noexcept;

// find absolute path, then split "/foo/bar/baz" into "/foo/bar" and "baz"
bool path_split(const char *in, char **dirname, char **basename) noexcept;

// Is a newer than b? Returns 1 for newer, 0 for older or equally old, -1 for error.
int path_isnewerthan(const char *a, const char *b) noexcept;

#ifdef __cplusplus
}   // extern "C"
#endif

#endif    // PATH_H
