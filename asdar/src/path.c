#include "path.h"
#include <errno.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

#if defined(_WIN32) || defined(_WIN64)
#define WINDOWS
#include <direct.h>
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

		// got the cwd, need to remove trailing slashes
		size_t len = strlen(buf);
		while (buf[len-1] == PATH_SLASH && len > 0)
			len--;
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
	char *res = path_concat_dotdot(cwd, path);
	free(cwd);
	if (!res)
		errno = ENOMEM;
	return res;
}

char *path_concat(const char *path1, const char *path2)
{
	size_t len1 = strlen(path1);
	size_t len2 = strlen(path2);

	if (len1 == 0)
		return duplicate_string(path2);
	// python returns 'asd/' for os.path.join('asd', ''), maybe that's good

	bool needslash = (path1[len1-1] != PATH_SLASH);
	char *res = malloc(len1 + (size_t)needslash + len2 + 1 /* for \0 */);
	if (!res) {
		errno = ENOMEM;
		return NULL;
	}

	memcpy(res, path1, len1);
	if (needslash) {
		res[len1] = PATH_SLASH;
		memcpy(res+len1+1, path2, len2+1);
	} else
		memcpy(res+len1, path2, len2+1);
	return res;
}

static inline bool starts_with_dotdotslash(const char *s)
{
	return s[0] == '.' && s[1] == '.' && s[2] == '/';
}

char *path_concat_dotdot(const char *path1, const char *path2)
{
	if (!starts_with_dotdotslash(path2))
		return path_concat(path1, path2);

	char *prefix = duplicate_string(path1);
	if (!prefix)
		return NULL;

	// must stop when prefix is empty string, otherwise "a" joined with "../../b" becomes "b"
	while (prefix[0] && starts_with_dotdotslash(path2)) {
		path2 += 3;    // 3 = length of "../"
		prefix[path_findlastslash(prefix)] = 0;
	}

	char *res = path_concat(prefix, path2);
	free(prefix);
	return res;   // may be NULL
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
