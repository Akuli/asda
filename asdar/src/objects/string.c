#include "string.h"
#include <assert.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include "err.h"
#include "func.h"
#include "../utf8.h"
#include "../interp.h"
#include "../objtyp.h"


static void destroy_string(struct Object *obj, bool decrefrefs, bool freenonrefs)
{
	struct StringObject *str = (struct StringObject *)obj;
	if (freenonrefs) {
		free(str->utf8cache);
		free(str->val);
	}
}

struct StringObject *stringobj_new_nocpy(Interp *interp, uint32_t *val, size_t len)
{
	struct StringObject *obj = object_new(interp, &stringobj_type, destroy_string, sizeof(*obj));
	if (!obj) {
		free(val);
		return NULL;
	}

	obj->val = val;
	obj->len = len;
	obj->utf8cache = NULL;
	return obj;
}

struct StringObject *stringobj_new(Interp *interp, const uint32_t *val, size_t len)
{
	uint32_t *valcp = malloc(sizeof(uint32_t)*len);
	if (len && !valcp) {   // malloc(0) is special
		errobj_set_nomem(interp);
		return NULL;
	}

	memcpy(valcp, val, sizeof(uint32_t)*len);
	return stringobj_new_nocpy(interp, valcp, len);
}

struct StringObject *stringobj_new_utf8(Interp *interp, const char *utf, size_t utflen)
{
	uint32_t *uni;
	size_t unilen;
	if (!utf8_decode(interp, utf, utflen, &uni, &unilen))
		return NULL;
	return stringobj_new_nocpy(interp, uni, unilen);
}


#define SMALL_SIZE 64
enum PartValKind { PVK_BIG_CONST, PVK_BIG_MALLOC, PVK_SMALL };
struct Part {
	enum PartValKind valkind;
	union {
		uint32_t small[SMALL_SIZE];
		const uint32_t *bigconst;
		uint32_t *bigmalloc;
	} val;
	size_t len;
};

static void destroy_part(struct Part part)
{
	if (part.valkind == PVK_BIG_MALLOC)
		free(part.val.bigmalloc);
}

// frees the bigmalloc vals of the parts
static struct StringObject *create_new_string_from_parts(Interp *interp, const struct Part *parts, size_t nparts)
{
	size_t lensum = 0;
	for (size_t i=0; i < nparts; i++)
		lensum += parts[i].len;

	if (lensum == 0) {
		for (size_t i=0; i < nparts; i++)
			destroy_part(parts[i]);
		return stringobj_new_nocpy(interp, NULL, 0);
	}

	uint32_t *buf = malloc(lensum * sizeof(buf[0]));
	if (!buf) {
		errobj_set_nomem(interp);
		goto error;
	}

	uint32_t *p = buf;
	for (size_t i=0; i < nparts; i++) {
		const uint32_t *val;
		switch(parts[i].valkind) {
			case PVK_BIG_MALLOC: val = parts[i].val.bigmalloc; break;
			case PVK_BIG_CONST:  val = parts[i].val.bigconst;  break;
			case PVK_SMALL:      val = parts[i].val.small;     break;
		}

		memcpy(p, val, parts[i].len * sizeof(p[0]));
		destroy_part(parts[i]);
		p += parts[i].len;
	}

	assert(p == buf+lensum);
	return stringobj_new_nocpy(interp, buf, lensum);

error:
	for (size_t i=0; i < nparts; i++)
		destroy_part(parts[i]);
	return NULL;
}


// there are table near ascii(7) man page
// from those, you see that '!' is first and '~' is last non-whitespace ascii char
#define IS_ASCII_PRINTABLE_NONWS(c) ('!' <= (c) && (c) <= '~')

static void short_ascii_to_part(const char *ascii, struct Part *part)
{
	part->valkind = PVK_SMALL;
	uint32_t *dst = part->val.small;
	const char *src = ascii;
	while (( *dst++ = (unsigned char)*src ))
		src++;
	part->len = (size_t)(src - ascii);
}

struct StringObject *stringobj_new_vformat(Interp *interp, const char *fmt, va_list ap)
{
	struct Part parts[20];
	size_t nparts = 0;

	while (*fmt) {
		if (fmt[0] != '%') {
			const char *end = strchr(fmt, '%');
			if (!end)
				end = fmt + strlen(fmt);

			parts[nparts].valkind = PVK_BIG_MALLOC;
			if (!utf8_decode(interp, fmt, (size_t)(end - fmt), &parts[nparts].val.bigmalloc, &parts[nparts].len))
				goto error;
			fmt = end;
			nparts++;
			continue;
		}

		char ascii[SMALL_SIZE];

		fmt++;   // skip '%'
		switch (*fmt++) {
		case 's':
		{
			const char *str = va_arg(ap, const char *);
			parts[nparts].valkind = PVK_BIG_MALLOC;
			if (!utf8_decode(interp, str, strlen(str), &parts[nparts].val.bigmalloc, &parts[nparts].len))
				goto error;
			break;
		}

		case 'd':
			sprintf(ascii, "%d", va_arg(ap, int));
			short_ascii_to_part(ascii, &parts[nparts]);
			break;

		case 'z':
		{
			char next = *fmt++;
			assert(next == 'u');
			sprintf(ascii, "%zu", va_arg(ap, size_t));
			short_ascii_to_part(ascii, &parts[nparts]);
			break;
		}

		case 'S':
		{
			struct StringObject *obj = va_arg(ap, struct StringObject *);
			parts[nparts].valkind = PVK_BIG_CONST;
			parts[nparts].val.bigconst = obj->val;
			parts[nparts].len = obj->len;
			break;
		}

		case 'U':
		{
			unsigned long u = va_arg(ap, uint32_t);
			if (IS_ASCII_PRINTABLE_NONWS(u))
				sprintf(ascii, "U+%04lX '%c'", u, (char)u);
			else
				sprintf(ascii, "U+%04lX", u);
			short_ascii_to_part(ascii, &parts[nparts]);
			break;
		}

		case 'B':
		{
			unsigned char b = (unsigned char) va_arg(ap, int);   // https://stackoverflow.com/q/28054194
			if (IS_ASCII_PRINTABLE_NONWS(b))
				sprintf(ascii, "0x%02x '%c'", (int)b, (char)b);
			else
				sprintf(ascii, "0x%02x", (int)b);

			short_ascii_to_part(ascii, &parts[nparts]);
			break;
		}

		case '%':
			short_ascii_to_part("%", &parts[nparts]);
			break;

		default:
			assert(0);
		}

		nparts++;
	}

	return create_new_string_from_parts(interp, parts, nparts);

error:
	for (size_t i = 0; i < nparts; i++)
		destroy_part(parts[i]);
	return NULL;
}

struct StringObject *stringobj_new_format(Interp *interp, const char *fmt, ...)
{
	va_list ap;
	va_start(ap, fmt);
	struct StringObject *res = stringobj_new_vformat(interp, fmt, ap);   // may be NULL
	va_end(ap);
	return res;  // may be NULL
}


bool stringobj_toutf8(struct StringObject *obj, const char **val, size_t *len)
{
	if( !obj->utf8cache &&
		!utf8_encode(obj->interp, obj->val, obj->len, &obj->utf8cache, &obj->utf8cachelen) )
	{
		obj->utf8cache = NULL;
		return false;
	}

	*val = obj->utf8cache;
	*len = obj->utf8cachelen;
	return true;
}

struct StringObject *stringobj_join(Interp *interp, struct StringObject *const *strs, size_t nstrs)
{
	if(nstrs == 0)
		return stringobj_new_nocpy(interp, NULL, 0);
	if(nstrs == 1) {
		OBJECT_INCREF(strs[0]);
		return strs[0];
	}

	struct Part *parts = malloc(nstrs * sizeof(parts[0]));
	if (!parts) {
		errobj_set_nomem(interp);
		return NULL;
	}

	for (size_t i = 0; i < nstrs; i++) {
		parts[i].valkind = PVK_BIG_CONST;
		parts[i].val.bigconst = strs[i]->val;
		parts[i].len = strs[i]->len;
	}

	struct StringObject *res = create_new_string_from_parts(interp, parts, nstrs);
	free(parts);
	return res;   // may be NULL
}


static bool tostring_impl(Interp *interp, struct ObjData data,
	struct Object *const *args, size_t nargs, struct Object **result)
{
	assert(nargs == 1);
	assert(args[0]->type == &stringobj_type);
	OBJECT_INCREF(args[0]);
	*result = args[0];
	return true;
}

static struct FuncObject tostring = FUNCOBJ_COMPILETIMECREATE(tostring_impl);

// TODO: first string method should be uppercase
static struct FuncObject *methods[] = { &tostring, &tostring };

const struct Type stringobj_type = { .methods = methods, .nmethods = sizeof(methods)/sizeof(methods[0]) };
