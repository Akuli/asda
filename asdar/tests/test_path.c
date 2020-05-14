#if defined(_WIN32) || defined(_WIN64)
	#define WINDOWS
#else
	#undef WINDOWS

	// for chdir()
	#define _POSIX_C_SOURCE 200809L
	#include <unistd.h>
#endif


#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include <src/path.h>
#include "util.h"

static bool endswith(const char *str, const char *end)
{
	size_t slen = strlen(str), elen = strlen(end);
	return slen >= elen && strcmp(str + slen - elen, end) == 0;
}

TEST(path_endswith_util)
{
	assert(endswith("abc", "abc"));
	assert(endswith("abc", "bc"));
	assert(!endswith("abc", "ab"));
}

TEST(path_isabsolute)
{
	assert(!path_isabsolute("asdf"));
	assert(!path_isabsolute("." PATH_SLASHSTR "asdf"));
	assert(!path_isabsolute(".." PATH_SLASHSTR "asdf"));

	if (PATH_SLASH == '/') {
		assert(path_isabsolute("/"));
		assert(path_isabsolute("/usr/bin"));
		assert(path_isabsolute("/usr/bin/"));
	} else {
		//assert(path_isabsolute("C:"));    // TODO: i don't know whether this is absolute
		assert(path_isabsolute("C:\\"));
		assert(path_isabsolute("C:\\Users"));
		assert(path_isabsolute("C:\\Users\\"));
	}
}

static void getcwd_stuff(void)
{
	char *cwd = path_getcwd();
	assert(cwd);
	assert(strlen(cwd) > 0);
	assert(path_isabsolute(cwd));
	free(cwd);
}

TEST(path_getcwd)
{
	getcwd_stuff();

#if !defined(WINDOWS)
	char *old = path_getcwd();
	chdir("/");
	getcwd_stuff();
	chdir(old);
	free(old);
#endif
}

TEST(path_toabsolute)
{
	char *cwd = path_getcwd();
	assert(path_isabsolute(cwd));

	char *abscwd = path_toabsolute(cwd);
	assert(strcmp(cwd, abscwd) == 0);
	free(abscwd);

	char *abslol = path_toabsolute("lol");
	assert(endswith(abslol, PATH_SLASHSTR "lol"));
	free(abslol);

	free(cwd);
}

TEST(path_concat)
{
	char *s = path_concat((const char *[]){ "a", "b", NULL }, 0);
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR "b");
	free(s);

	s = path_concat((const char *[]){ "a", "", NULL }, 0);
	assert_cstr_eq_cstr(s, "a");
	free(s);

	s = path_concat((const char *[]){ "", "b", NULL }, 0);
	assert_cstr_eq_cstr(s, "b");
	free(s);

	s = path_concat((const char *[]){ "a", "..", "b", NULL }, 0);
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR ".." PATH_SLASHSTR "b");
	free(s);
}

TEST(path_concat_dotdot)
{
	char *s = path_concat((const char *[]){ "a", "b", NULL }, PATH_RMDOTDOT);
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR "b");
	free(s);

	s = path_concat((const char *[]){ "a", "..", "b", NULL }, PATH_RMDOTDOT);
	assert_cstr_eq_cstr(s, "b");
	free(s);

	s = path_concat((const char *[]){ "a", "..", NULL }, PATH_RMDOTDOT);
	assert_cstr_eq_cstr(s, "");
	free(s);

	s = path_concat((const char *[]){ "a", "..", "..", "..", "b", NULL }, PATH_RMDOTDOT);
	assert_cstr_eq_cstr(s, "b");
	free(s);

	s = path_concat((const char *[]){ "a", "b", "..", "c", NULL }, PATH_RMDOTDOT);
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR "c");
	free(s);

	s = path_concat((const char *[]){ "a", "b", "c", ".."PATH_SLASHSTR".."PATH_SLASHSTR"foo", NULL }, PATH_RMDOTDOT);
	assert_cstr_eq_cstr(s, "a"PATH_SLASHSTR"foo");
	free(s);

	s = path_concat((const char *[]){ "a", ".."PATH_SLASHSTR".."PATH_SLASHSTR"foo", NULL }, PATH_RMDOTDOT);
	assert_cstr_eq_cstr(s, ".."PATH_SLASHSTR"foo");
	free(s);
}

TEST(path_findlastslash)
{
	assert(path_findlastslash("") == 0);
	assert(path_findlastslash("asd") == 0);
	assert(path_findlastslash("asd" PATH_SLASHSTR "blah") == 3);
	assert(path_findlastslash("asd" PATH_SLASHSTR "blah" PATH_SLASHSTR) == 3);
	assert(path_findlastslash("asd" PATH_SLASHSTR "blah" PATH_SLASHSTR PATH_SLASHSTR) == 3);
}

TEST(path_isnewerthan)
{
	const char *path = "temp file for tests";
	fclose(fopen(path, "w"));

	assert(path_isnewerthan(path, "README.md") == 1);
	assert(path_isnewerthan("README.md", path) == 0);
	assert(path_isnewerthan("README.md", "README.md") == 0);
	assert(path_isnewerthan("this doesnt exist", "README.md") == -1);
	assert(path_isnewerthan("README.md", "this doesnt exist") == -1);

	remove(path);
}
