#include "path.h"

#include <cassert>
#include <cerrno>
#include <vector>
#include <stdlib.h>
#include <system_error>
#include <filesystem>

namespace {

char *cppstring_to_cstring(const std::string& s)
{
	char *cstr = (char *) malloc(s.length() + 1);
	if (!cstr)
		throw std::bad_alloc();

	std::copy(s.begin(), s.end(), cstr);
	cstr[s.length()] = 0;
	return cstr;
}

void handle_system_error(const std::system_error& e)
{
	errno = e.code().value();
}

// symlinks don't work nicely with this
std::filesystem::path remove_dotdots_dumbly(const std::filesystem::path& p)
{
	std::vector<std::string> parts;
	for (const std::string& elem : p) {
		if (elem == ".." && !parts.empty())
			parts.pop_back();
		else
			parts.push_back(elem);
	}

	if (parts.empty())
		return std::filesystem::path(".");

	std::filesystem::path res(parts[0]);
	auto it = parts.begin();
	it++;
	while (it != parts.end())
		res /= *it++;
	return res;
}

}  // anonymous namespace


extern "C" {

char *path_getcwd(void)
{
	try {
		std::filesystem::path path = std::filesystem::current_path();
		return cppstring_to_cstring(path);
	}
	catch (std::system_error& e) { handle_system_error(e); return nullptr; }
	catch (std::bad_alloc& e) { errno = ENOMEM; return nullptr; }
}

bool path_isabsolute(const char *pathstr)
{
	try {
		std::filesystem::path path(pathstr);
		return path.is_absolute();
	}
	catch (std::system_error& e) { handle_system_error(e); return false; }
	catch (std::bad_alloc& e) { errno = ENOMEM; return false; }
}

char *path_concat(const char *const *paths, enum PathConcatFlags flags)
{
	assert(paths[0]);

	try {
		std::filesystem::path path(paths[0]);
		if (flags & PATH_FIRSTPARENT)
			path = path.parent_path();

		for (size_t i = 1; paths[i]; i++) {
			std::filesystem::path add(paths[i]);
			path /= add;
		}

		if ((flags & PATH_RMDOTDOT) || (flags & PATH_RMDOTDOT_DUMB)) {
			try {
				path = std::filesystem::canonical(path);
			} catch (std::system_error& e) {   // no std::filesystem_error in gcc
				if (flags & PATH_RMDOTDOT_DUMB) {
					path = remove_dotdots_dumbly(path);
				}
			}
		}
		return cppstring_to_cstring(path);
	}
	catch (std::system_error& e) { handle_system_error(e); return nullptr; }
	catch (std::bad_alloc& e) { errno = ENOMEM; return nullptr; }
}

bool path_split(const char *in, char **dirname, char **basename)
{
	*dirname = NULL;
	*basename = NULL;

	try {
		std::filesystem::path path(in);
		path = std::filesystem::canonical(path);
		*dirname = cppstring_to_cstring(path.parent_path());
		*basename = cppstring_to_cstring(path.filename());
	}
	catch (std::system_error& e) { handle_system_error(e); goto error; }
	catch (std::bad_alloc& e) { errno = ENOMEM; goto error; }

	assert(*dirname);
	assert(*basename);
	return true;

error:
	free(*dirname);
	free(*basename);
	return false;
}


int path_isnewerthan(const char *a, const char *b)
{
	try {
		std::filesystem::file_time_type
			atime = std::filesystem::last_write_time(a),
			btime = std::filesystem::last_write_time(b);
		return (atime > btime);
	}
	catch (std::system_error& e) { handle_system_error(e); return -1; }
	catch (std::bad_alloc& e) { errno = ENOMEM; return -1; }
}

}   // extern "C"
