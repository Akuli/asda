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

TEST(path_getcwd)
{
	char *cwd = path_getcwd();
	assert(cwd);
	assert(strlen(cwd) > 0);
	assert(path_isabsolute(cwd));
	free(cwd);
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
	char *s = path_concat("a", "b");
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR "b");
	free(s);

	s = path_concat("a", "");
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR);
	free(s);

	s = path_concat("", "b");
	assert_cstr_eq_cstr(s, "b");
	free(s);

	s = path_concat("a", ".." PATH_SLASHSTR "b");
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR ".." PATH_SLASHSTR "b");
	free(s);

	s = path_concat("a" PATH_SLASHSTR "..", "b");
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR ".." PATH_SLASHSTR "b");
	free(s);
}

TEST(path_concat_dotdot)
{
	char *s = path_concat_dotdot("a" PATH_SLASHSTR "b", ".." PATH_SLASHSTR "c");
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR "c");
	free(s);

	s = path_concat_dotdot("a", ".." PATH_SLASHSTR "b");
	assert_cstr_eq_cstr(s, "b");
	free(s);

	s = path_concat_dotdot("a", "b");
	assert_cstr_eq_cstr(s, "a" PATH_SLASHSTR "b");
	free(s);

	s = path_concat_dotdot("a", ".." PATH_SLASHSTR "b");
	assert_cstr_eq_cstr(s, "b");
	free(s);

	s = path_concat_dotdot("a", ".." PATH_SLASHSTR ".." PATH_SLASHSTR "b");
	assert_cstr_eq_cstr(s, ".." PATH_SLASHSTR "b");
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
