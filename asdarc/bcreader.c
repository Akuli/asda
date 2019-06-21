#include "bcreader.h"
#include <stdlib.h>
#include <string.h>
#include "path.h"
#include "objects/string.h"

#define END_OF_BODY 'E'
#define SET_VAR 'V'
#define GET_VAR 'v'
#define IMPORT_SECTION 'i'
#define SET_LINENO 'L'
#define STR_CONSTANT '"'

// from the tables in ascii(7), we see that '!' is first printable ascii char and '~' is last
#define is_printable_ascii(c) ('!' <= (c) && (c) <= '~')


struct BcReader bcreader_new(struct Interp *interp, FILE *in, const char *indirname)
{
	struct BcReader res;
	res.interp = interp;
	res.in = in;
	res.indirname = indirname;
	res.lineno = 1;
	return res;
}


static bool read_bytes(struct BcReader *bcr, unsigned char *buf, size_t n)
{
	if (fread(buf, 1, n, bcr->in) == n)
		return true;

	if (feof(bcr->in))
		strcpy(bcr->interp->errstr, "unexpected end of file");
	else
		strcpy(bcr->interp->errstr, "reading failed");
	return false;
}


// this is little-endian
#define CREATE_UINT_READER(N) \
static bool read_uint ## N (struct BcReader *bcr, uint ## N ## _t *res) \
{ \
	unsigned char buf[N/8]; \
	if (!read_bytes(bcr, buf, N/8)) \
		return false; \
	\
	*res = 0; \
	for (int i = 0; i < N/8; i++) { \
		*res = (uint ## N ## _t)(*res | ((uint ## N ## _t)buf[i] << (8*i))); \
	} \
	return true; \
}

CREATE_UINT_READER(8)
CREATE_UINT_READER(16)
CREATE_UINT_READER(32)


static bool read_string(struct BcReader *bcr, char **str, uint32_t *len)
{
	if (!read_uint32(bcr, len))
		return false;

	// len+1 so that adding 0 byte will be easy if needed, and empty string is not a special case
	if (!( *str = malloc((*len)+1) )) {
		*len = 0;
		sprintf(bcr->interp->errstr, "not enough memory for a string of %lu characters", (unsigned long)len);
		return false;
	}
	if (!read_bytes(bcr, (unsigned char*) *str, *len)) {
		free(*str);
		*len = 0;
		return false;
	}
	return true;
}

static bool read_string0(struct BcReader *bcr, char **str)
{
	uint32_t len;
	if (!read_string(bcr, str, &len))
		return false;

	(*str)[len] = 0;
	if (strlen(*str) < (size_t)len) {
		strcpy(bcr->interp->errstr, "unexpected 0 byte in string");
		free(*str);
		return false;
	}
	return true;
}

static bool read_path(struct BcReader *bcr, char **path)
{
	if (!read_string0(bcr, path))
		return false;

	// lowercasing on windows is not needed here, compiler takes care of all that

	for (char *p = *path; *p; p++)
		if (*p == '/')
			*p = PATH_SLASH;

	return true;
}


#define ASDABYTES "asda"

bool bcreader_readasdabytes(struct BcReader *bcr)
{
	unsigned char buf[sizeof(ASDABYTES)-1];
	if (!read_bytes(bcr, buf, sizeof buf))
		return false;

	if (memcmp(buf, ASDABYTES, sizeof(buf)) == 0)
		return true;
	strcpy(bcr->interp->errstr, "the file doesn't seem to be a compiled asda file");
	return false;
}

bool bcreader_readimports(struct BcReader *bcr, char ***paths, uint16_t *npaths)
{
	*paths = NULL;
	*npaths = 0;
	char **ptr;

	unsigned char b;
	if (!read_bytes(bcr, &b, 1))
		goto error;
	if (b != IMPORT_SECTION) {
		sprintf(bcr->interp->errstr, "expected import section, got %#x", (int)b);
		goto error;
	}
	if (!read_uint16(bcr, npaths))
		goto error;

	if (npaths == 0) {
		return true;
	}

	*paths = malloc(sizeof(char*) * *npaths);
	if (!*paths) {
		strcpy(bcr->interp->errstr, "not enough memory");
		goto error;
	}

	for (ptr = *paths; ptr < *paths + *npaths; ptr++) {
		if (!read_path(bcr, ptr))
			goto error;
	}

	printf("npaths = %d\n", (int)(*npaths));

	return true;

error:
	if (*paths) {
		while (--ptr >= *paths)
			free(*ptr);
		free(*paths);
	}
	*paths = NULL;
	*npaths = 0;
	return false;
}

void bcreader_freeimports(char **paths, uint16_t npaths)
{
	for (char **ptr = paths; ptr < paths + npaths; ptr++)
		free(*ptr);
	free(paths);
}


static bool read_opbyte(struct BcReader *bcr, struct Bc *bc, unsigned char *ob)
{
	if (!read_bytes(bcr, ob, 1)) return false;
	if (*ob == SET_LINENO) {
		if (!read_uint32(bcr, &bcr->lineno)) return false;
		if (!read_bytes(bcr, ob, 1)) return false;
		if (*ob == SET_LINENO) {
			sprintf(bcr->interp->errstr, "repeated lineno byte '%c'", SET_LINENO);
			return false;
		}
	}
	return true;
}

static bool read_vardata(struct BcReader *bcr, struct BcOp *res, enum BcOpKind kind)
{
	struct BcVarData vd;
	if (!read_uint8(bcr, &vd.level)) return false;
	if (!read_uint16(bcr, &vd.index)) return false;

	res->data.var = vd;
	res->kind = kind;
	return true;
}

static bool read_op(struct BcReader *bcr, unsigned char opbyte, struct BcOp *res)
{

	switch(opbyte) {
	case STR_CONSTANT:
	{
		char *str;
		uint32_t len;
		if (!read_string(bcr, &str, &len))
			return false;

		struct Object *obj = stringobj_newfromutf8(bcr->interp, str, len);
		free(str);
		if(!obj)
			return false;

		res->kind = BC_CONSTANT;
		res->data.obj = obj;
		return true;
	}

	case SET_VAR:
		return read_vardata(bcr, res, BC_SETVAR);
	case GET_VAR:
		return read_vardata(bcr, res, BC_GETVAR);

	default:
		sprintf(bcr->interp->errstr, "unknown op byte: %#x", (int)opbyte);
		if (is_printable_ascii(opbyte))
			sprintf(bcr->interp->errstr + strlen(bcr->interp->errstr), " '%c'", opbyte);
		return false;
	}
}

static bool read_body(struct BcReader *bcr, struct Bc *bc)
{
	uint16_t nlocals;
	if (!read_uint16(bcr, &nlocals))
		return false;

	struct BcOp *first = NULL;
	struct BcOp *last = NULL;

	while(true) {
		unsigned char ob;
		if (!read_opbyte(bcr, bc, &ob))
			goto error;
		if (ob == END_OF_BODY)
			break;

		struct BcOp val;
		val.lineno = bcr->lineno;
		val.next = NULL;
		// val.kind and val.data must be set in read_op()

		if (!read_op(bcr, ob, &val))
			goto error;

		if (!( last = bcop_append(bcr->interp, last) )) {
			bcop_destroy(&val);
			goto error;
		}
		*last = val;
		if (!first)
			first = last;
	}

	bc->firstop = first;
	bc->nlocalvars = nlocals;
	return true;

error:
	bcop_destroylist(first);
	return false;
}

bool bcreader_readcodepart(struct BcReader *bcr, struct Bc *bc)
{
	// TODO: check byte after body
	return read_body(bcr, bc);
}
