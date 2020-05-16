#include "string.h"
#include <assert.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "bool.h"
#include "err.h"
#include "int.h"
#include "../utf8.h"
#include "../interp.h"
#include "../object.h"

StringObject stringobj_empty = STRINGOBJ_COMPILETIMECREATE("");


static void setup_string_object(StringObject *obj, size_t utf8len)
{
	obj->utf8len = utf8len;
	obj->utf8ct = NULL;
	obj->utf8rt[utf8len] = '\0';
}

// creates a copy of the utf8 and uses that
// utf8 doesn't need to be '\0' terminated
// make sure that you are not passing in invalid utf8 (use utf8_validate with user inputs)
// if utf8 is NULL, then the content is left uninitialized, must get filled immediately after calling
StringObject *stringobj_new(Interp *interp, const char *utf8, size_t utf8len)
{
	if (utf8)
		assert(utf8_validate(NULL, utf8, utf8len));
	if (utf8len == 0) {
		OBJECT_INCREF(&stringobj_empty);
		return &stringobj_empty;
	}

	StringObject *obj = object_new(interp, NULL, sizeof(*obj) + utf8len + 1);
	if (!obj)
		return NULL;

	if (utf8)
		memcpy(obj->utf8rt, utf8, utf8len);
	setup_string_object(obj, utf8len);
	return obj;
}

StringObject *stringobj_new_nocp(Interp *interp, char *utf8, size_t utf8len)
{
	if (utf8len == 0 || !utf8) {
		free(utf8);
		return stringobj_new(interp, NULL, utf8len);
	}

	// make room for object stuff
	void *ptr = realloc(utf8, sizeof(StringObject) + utf8len + 1);
	if (!ptr) {
		free(utf8);
		errobj_set_nomem(interp);
		return NULL;
	}
	utf8 = ptr;

	// add object stuff to beginning of utf8
	memmove(utf8 + sizeof(StringObject), utf8, utf8len);
	object_init(interp, NULL, ptr);
	setup_string_object(ptr, utf8len);
	return ptr;
}

const char *stringobj_getutf8(StringObject *s)
{
	if (s->utf8ct)
		return s->utf8ct;
	return s->utf8rt;
}


// there are table near ascii(7) man page
// from those, you see that '!' is first and '~' is last non-whitespace ascii char
#define IS_ASCII_PRINTABLE_NONWS(c) ('!' <= (c) && (c) <= '~')


// typedef needed because every occurence of DynArray(char) is a new, different type
typedef DynArray(char) Buf;   // NOT necessarily '\0'-terminated

static bool chars_to_buf(Interp *interp, Buf *buf, const char *chars, size_t len)
{
	if (!dynarray_alloc(interp, buf, buf->len + len))
		return false;
	memcpy(&buf->ptr[buf->len], chars, len);
	buf->len += len;
	return true;
}

StringObject *stringobj_new_vformat(Interp *interp, const char *fmt, va_list ap)
{
	Buf buf;
	dynarray_init(&buf);

	while (*fmt) {
		if (fmt[0] != '%') {
			const char *end = strchr(fmt, '%');
			size_t len = end ? (size_t)(end - fmt) : strlen(fmt);
			if (!chars_to_buf(interp, &buf, fmt, len))
				goto error;

			fmt += len;
			continue;
		}

		fmt++;   // skip '%'

		unsigned char uc;
		char c;
		char smol[64];
		const char *str;
		StringObject *strobj;
		int i;
		size_t sz;
		unsigned long ul;

		switch(*fmt++) {
		case 's':
			str = va_arg(ap, const char*);
			sz = strlen(str);
			if (!utf8_validate(interp, str, sz) || !chars_to_buf(interp, &buf, str, sz))
				goto error;
			break;

		case 'd':
			i = sprintf(smol, "%d", va_arg(ap, int));
			assert(0 < i && i < (int)sizeof(smol));
			if (!chars_to_buf(interp, &buf, smol, (size_t)i))
				goto error;
			break;

		case 'z':
			c = *fmt++;
			assert(c == 'u');

			i = sprintf(smol, "%zu", va_arg(ap, size_t));
			assert(0 < i && i < (int)sizeof(smol));
			if (!chars_to_buf(interp, &buf, smol, (size_t)i))
				goto error;
			break;

		case 'S':
			strobj = va_arg(ap, StringObject *);
			if (!chars_to_buf(interp, &buf, stringobj_getutf8(strobj), strobj->utf8len))
				goto error;
			break;

		case 'B':
			uc = (unsigned char) va_arg(ap, int);   // https://stackoverflow.com/q/28054194
			if (IS_ASCII_PRINTABLE_NONWS(uc))
				i = sprintf(smol, "0x%02x '%c'", (int)uc, (char)uc);
			else
				i = sprintf(smol, "0x%02x", (int)uc);

			assert(0 < i && i < (int)sizeof(smol));
			if (!chars_to_buf(interp, &buf, smol, (size_t)i))
				goto error;
			break;

		case 'U':
			ul = va_arg(ap, uint32_t);
			if (IS_ASCII_PRINTABLE_NONWS(ul))
				i = sprintf(smol, "U+%04lX '%c'", ul, (char)ul);
			else
				i = sprintf(smol, "U+%04lX", ul);

			assert(0 < i && i < (int)sizeof(smol));
			if (!chars_to_buf(interp, &buf, smol, (size_t)i))
				goto error;
			break;

		case '%':
			if (!dynarray_push(interp, &buf, '%'))
				goto error;
			break;
		}
	}

	return stringobj_new_nocp(interp, buf.ptr, buf.len);   // may be NULl

error:
	free(buf.ptr);
	return NULL;
}

StringObject *stringobj_new_format(Interp *interp, const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	StringObject *res = stringobj_new_vformat(interp, fmt, ap);   // may be NULL
	va_end(ap);
	return res;  // may be NULL
}


bool stringobj_eq(StringObject *a, StringObject *b)
{
	if (a->utf8len != b->utf8len)
		return false;
	return memcmp(stringobj_getutf8(a), stringobj_getutf8(b), a->utf8len) == 0;
}

StringObject *stringobj_join(Interp *interp, StringObject *const *strs, size_t nstrs)
{
	if(nstrs == 0) {
		OBJECT_INCREF(&stringobj_empty);
		return &stringobj_empty;
	}

	size_t totlen = 0;
	for (size_t i = 0; i < nstrs; i++)
		totlen += strs[i]->utf8len;

	StringObject *res = stringobj_new(interp, NULL, totlen);
	if (!res)
		return NULL;

	char *ptr = res->utf8rt;
	assert(ptr);
	for (size_t i = 0; i < nstrs; i++) {
		memcpy(ptr, stringobj_getutf8(strs[i]), strs[i]->utf8len);
		ptr += strs[i]->utf8len;
	}
	assert(ptr == res->utf8rt + totlen);

	return res;
}


// not strictly a string function, but there's not much more io stuff than this yet
static bool print_cfunc(Interp *interp, Object *const *args)
{
	StringObject *sobj = (StringObject*)args[0];
	const char *utf8 = stringobj_getutf8(sobj);

	if (fwrite(utf8, 1, sobj->utf8len, stdout) != sobj->utf8len
		|| putchar('\n') == EOF)
	{
		errobj_set_oserr(interp, "cannot write to stdout");
		return false;
	};
	return true;
}

static Object *eq_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) boolobj_c2asda(stringobj_eq((StringObject *) args[0], (StringObject *) args[1]));
}

static Object *plus_cfunc(Interp *interp, Object *const *args)
{
	return (Object *) stringobj_join(interp, (StringObject *const *) args, 2);
}

// TODO: should calculate unicode length? or display length with wcwidth?
// i wouldn't want to depend on the current locale......
/*
static Object *getlength_cfunc(Interp *interp,	Object *const *args)
{
	StringObject *s = (StringObject *) args[0];
	return (Object*)intobj_new_long(interp, (long) s->len);
}
*/

const struct CFunc stringobj_cfuncs[] = {
	{ "print", 1, false, { .noret = print_cfunc }},
	{ "Str==Str", 2, true, { .ret = eq_cfunc }},
	{ "Str+Str", 2, true, { .ret = plus_cfunc }},
	//{ "Str.get_length", 1, true, { .ret = getlength_cfunc }},
	{0},
};
