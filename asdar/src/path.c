#include "path.h"
#include <assert.h>
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>

/*
the order of these matters, at least according to windows docs: "Because STAT.H
uses the _dev_t type that is defined in TYPES.H, you must include TYPES.H before
STAT.H in your code."
*/
#include <sys/types.h>
#include <sys/stat.h>

#if defined(_WIN32) || defined(_WIN64)
	#define WINDOWS
	#include <direct.h>

	// this works for the function named _stat AND the struct named _stat
	#define stat _stat
#else
	#undef WINDOWS
	#include <unistd.h>
#endif


// this is one of the not-so-many things that windows makes easy... :D
char *path_getcwd(void)
{
#ifdef WINDOWS
	// https://msdn.microsoft.com/en-us/library/sf98bd4y.aspx
	// "The buffer argument can be NULL; a buffer of at least size maxlen (more only
	//  if necessary) is automatically allocated, using malloc, to store the path."
	// and in the "Return Value" section:
	// "A NULL return value indicates an error, and errno is set either to ENOMEM,
	//  indicating that there is insufficient memory to allocate maxlen bytes (when
	//  a NULL argument is given as buffer), or [...]"
	return _getcwd(NULL, 1);

#else
	// unixy getcwd() wants a buffer of fixed size
	char *buf = NULL;
	for (size_t bufsize = 64; ; bufsize *= 2) {
		void *tmp = realloc(buf, bufsize);     // mallocs if buf is NULL
		if (!tmp) {
			free(buf);
			errno = ENOMEM;
			return NULL;
		}
		buf = tmp;

		if (!getcwd(buf, bufsize)) {
			if (errno == ERANGE)     // buffer was too small
				continue;
			free(buf);
			return NULL;
		}

		// got the cwd, need to remove trailing slashes but not strip "/" to ""
		size_t len = strlen(buf);
		while (len >= 2 && buf[len-1] == PATH_SLASH)
			len--;
		buf[len] = '\0';
		return buf;
	}

#endif
}

bool path_isabsolute(const char *path)
{
#ifdef WINDOWS
	// "\asd\toot" is equivalent to "X:\asd\toot" where X is... the drive of cwd i guess?
	// path[0] is '\0' if the path is empty
	if (path[0] == '\\')
		return true;

	// check for X:\asdasd
	return (('A' <= path[0] && path[0] <= 'Z') || ('a' <= path[0] && path[0] <= 'z')) &&
		path[1] == ':' && path[2] == '\\';

#else
	return path[0]=='/';

#endif
}

static inline bool is_dotdot(const char *s)
{
	return (strcmp(s, "..") == 0);
}

static inline bool starts_with_dotdotslash(const char *s)
{
	return (strncmp(s, ".." PATH_SLASHSTR, 3) == 0);
}

char *path_concat(const char *const *paths, enum PathConcatFlags flags)
{
	size_t sz = 1;   // for '\0'
	for (size_t i = 0; paths[i]; i++) {
		sz += strlen(paths[i]) + 1;   // +1 for PATH_SLASH
	}

	char *res = malloc(sz);
	if (!res) {
		errno = ENOMEM;
		return NULL;
	}

	res[0] = '\0';

	for (size_t i = 0; paths[i]; i++) {
		const char *add = paths[i];

		if ( flags & PATH_RMDOTDOT ){
			while (res[0] && (is_dotdot(add) || starts_with_dotdotslash(add)))
			{
				size_t k = path_findlastslash(res);
				if (k == 0 && path_isabsolute(res))  // avoid "/foo" --> "/" --> "". TODO: windows
					break;

				res[k] = '\0';
				if (is_dotdot(add))
					add = "";
				else
					add += strlen("../");
			}
		}

		if (add[0]) {
			if (res[0] && res[strlen(res) - 1] != PATH_SLASH)
				strcat(res, PATH_SLASHSTR);
			strcat(res, add);
		}
	}

	if (flags & PATH_RMDOTDOT) {
		// free up any memory that we didn't end up needing after all
		res = realloc(res, strlen(res) + 1);
		assert(res);
	}
	return res;
}

// strdup is non-standard
static char *duplicate_string(const char *src)
{
	char *res = malloc(strlen(src) + 1);
	if (!res) {
		errno = ENOMEM;
		return NULL;
	}
	strcpy(res, src);
	return res;
}

char *path_toabsolute(const char *path)
{
	if (path_isabsolute(path))
		return duplicate_string(path);

	char *cwd = path_getcwd();
	if (!cwd)
		return NULL;

	// TODO: figure out how to do this without symlink issues and ".."
	char *res = path_concat((const char *[]){cwd, path, NULL}, PATH_RMDOTDOT);
	free(cwd);
	return res;
}

size_t path_findlastslash(const char *path)
{
	if (path[0] == 0)
		return 0;

	// ignore trailing slashes
	// they are also the reason why strrchr() isn't useful here
	size_t i = strlen(path)-1;
	while (i >= 1 && path[i] == PATH_SLASH)
		i--;

	// TODO: i think C:blah.txt is a valid windows path??
	for (; i >= 1; i-- /* behaves well because >=1 */)
	{
		if (path[i] == PATH_SLASH)
			return i;
	}
	return 0;
}


// this is borrowed from libbsd-dev, file /usr/include/bsd/sys/time.h
#define	timespeccmp(tsp, usp, cmp)					\
	(((tsp)->tv_sec == (usp)->tv_sec) ?				\
	    ((tsp)->tv_nsec cmp (usp)->tv_nsec) :			\
	    ((tsp)->tv_sec cmp (usp)->tv_sec))

int path_isnewerthan(const char *a, const char *b)
{
	struct stat astat, bstat;
	if (stat(a, &astat) != 0 || stat(b, &bstat) != 0)
		return -1;

// look carefully, st_mtim and st_mtime are different things
#if defined(st_mtime)
	/*	We have nanosecond precision st_mtim, and st_mtime is a backwards
		compatibility alias. This is the case on e.g. Linux. */
	return timespeccmp(astat.st_mtim, bstat.st_mtim, >);
#else
	// e.g. windows
	return difftime(astat.st_mtime, bstat.st_mtime) > 0;
#endif
}
