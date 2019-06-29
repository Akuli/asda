#include "bcreader.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "bc.h"
#include "builtin.h"
#include "objtyp.h"
#include "path.h"
#include "objects/bool.h"
#include "objects/string.h"
#include "objects/int.h"

#define IMPORT_SECTION 'i'
#define SET_VAR 'V'
#define GET_VAR 'v'
#define SET_LINENO 'L'
#define STR_CONSTANT '"'
#define TRUE_CONSTANT 'T'
#define FALSE_CONSTANT 'F'
#define CALL_VOID_FUNCTION '('
#define CALL_RETURNING_FUNCTION ')'
#define BOOLNEG '!'
#define JUMPIF 'J'
#define STRING_JOIN 'j'
#define GET_METHOD '.'   // currently all attributes are methods
#define NON_NEGATIVE_INT_CONSTANT '1'
#define NEGATIVE_INT_CONSTANT '2'
#define INT_ADD '+'
#define INT_SUB '-'
#define INT_NEG '_'
#define INT_MUL '*'
#define END_OF_BODY 'E'

#define TYPEBYTE_BUILTIN 'b'

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
	else   // TODO: include file name in error msg
		interp_errstr_printf_errno(bcr->interp, "reading failed");
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
	for (int i = 0; i < N/8; i++) \
		*res = (uint ## N ## _t)(*res | ((uint ## N ## _t)buf[i] << (8*i))); \
	return true; \
}

CREATE_UINT_READER(8)
CREATE_UINT_READER(16)
CREATE_UINT_READER(32)

#undef CREATE_UINT_READER


static bool read_string(struct BcReader *bcr, char **str, uint32_t *len)
{
	if (!read_uint32(bcr, len))
		return false;

	// len+1 so that adding 0 byte will be easy if needed, and empty string is not a special case
	if (!( *str = malloc((*len)+1) )) {
		*len = 0;
		interp_errstr_nomem(bcr->interp);
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


bool bcreader_readasdabytes(struct BcReader *bcr)
{
	unsigned char buf[sizeof("asda")-1];
	if (!read_bytes(bcr, buf, sizeof buf))
		return false;

	if (memcmp(buf, "asda", sizeof(buf)) == 0)
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
		interp_errstr_printf(bcr->interp, "expected import section, got %#x", (int)b);
		goto error;
	}
	if (!read_uint16(bcr, npaths))
		goto error;

	if (npaths == 0) {
		return true;
	}

	*paths = malloc(sizeof(char*) * *npaths);
	if (!*paths) {
		interp_errstr_nomem(bcr->interp);
		goto error;
	}

	for (ptr = *paths; ptr < *paths + *npaths; ptr++) {
		if (!read_path(bcr, ptr))
			goto error;
	}

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


static void append_byte_2_errstr(struct Interp *interp, unsigned char byte)
{
	char *ptr = interp->errstr + strlen(interp->errstr);
	char *max = interp->errstr + sizeof(interp->errstr);
	if(max-ptr < 2)   // need at least 1 byte to write stuff to, 1 byte for \0, otherwise would be useless
		return;

	if(is_printable_ascii(byte))
		snprintf(ptr, (size_t)(max-ptr), ": %#x '%c'", (int)byte, byte);
	else
		snprintf(ptr, (size_t)(max-ptr), ": %#x", (int)byte);
}


static bool read_opbyte(struct BcReader *bcr, unsigned char *ob)
{
	if (!read_bytes(bcr, ob, 1)) return false;
	if (*ob == SET_LINENO) {
		if (!read_uint32(bcr, &bcr->lineno)) return false;
		if (!read_bytes(bcr, ob, 1)) return false;
		if (*ob == SET_LINENO) {
			interp_errstr_printf(bcr->interp, "repeated lineno byte");
			append_byte_2_errstr(bcr->interp, SET_LINENO);
			return false;
		}
	}
	return true;
}

const struct Type *read_type(struct BcReader *bcr)
{
	// TODO: many types missing here
	unsigned char byte;
	if(!read_bytes(bcr, &byte, 1))
		return NULL;

	switch(byte) {
	case TYPEBYTE_BUILTIN:
	{
		uint8_t i;
		if (!read_uint8(bcr, &i))
			return NULL;
		assert(i < builtin_ntypes);
		return builtin_types[i];
	}

	default:
		interp_errstr_printf(bcr->interp, "unknown type byte");
		append_byte_2_errstr(bcr->interp, byte);
		return NULL;
	}
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

static bool read_callfunc(struct BcReader *bcr, struct BcOp *res, enum BcOpKind kind)
{
	res->kind = kind;
	return read_uint8(bcr, &res->data.callfunc_nargs);
}

static bool read_string_constant(struct BcReader *bcr, struct Object **objptr)
{
	char *str;
	uint32_t len;
	if (!read_string(bcr, &str, &len))
		return false;

	*objptr = stringobj_new_utf8(bcr->interp, str, len);
	free(str);
	return !!*objptr;
}

static bool read_int_constant(struct BcReader *bcr, struct Object **objptr, bool negate)
{
	uint32_t len;
	if(!read_uint32(bcr, &len))
		return false;

	unsigned char *buf = malloc(len);
	if(!buf) {
		interp_errstr_nomem(bcr->interp);
		return false;
	}

	if(!read_bytes(bcr, buf, len)) {
		free(buf);
		return false;
	}

	*objptr = intobj_new_bebytes(bcr->interp, buf, len, negate);
	free(buf);
	return !!*objptr;
}

static bool read_op(struct BcReader *bcr, unsigned char opbyte, struct BcOp *res)
{
	switch(opbyte) {
	case STR_CONSTANT:
		res->kind = BC_CONSTANT;
		return read_string_constant(bcr, &res->data.obj);

	case TRUE_CONSTANT:
	case FALSE_CONSTANT:
		res->kind = BC_CONSTANT;
		res->data.obj = boolobj_c2asda(opbyte == TRUE_CONSTANT);
		return true;

	case SET_VAR:
		return read_vardata(bcr, res, BC_SETVAR);
	case GET_VAR:
		return read_vardata(bcr, res, BC_GETVAR);
	case CALL_VOID_FUNCTION:
		return read_callfunc(bcr, res, BC_CALLVOIDFUNC);
	case CALL_RETURNING_FUNCTION:
		return read_callfunc(bcr, res, BC_CALLRETFUNC);
	case BOOLNEG:
		res->kind = BC_BOOLNEG;
		return true;
	case JUMPIF:
		res->kind = BC_JUMPIF;
		return read_uint16(bcr, &res->data.jump_idx);
	case NON_NEGATIVE_INT_CONSTANT:
	case NEGATIVE_INT_CONSTANT:
		res->kind = BC_CONSTANT;
		return read_int_constant(bcr, &res->data.obj, opbyte==NEGATIVE_INT_CONSTANT);
	case GET_METHOD:
		res->kind = BC_GETMETHOD;
		if (!( res->data.lookupmethod.type = read_type(bcr) ))
			return false;
		if (!read_uint16(bcr, &res->data.lookupmethod.index))
			return false;
		assert(res->data.lookupmethod.index < res->data.lookupmethod.type->nmethods);
		return true;

	case STRING_JOIN:
		res->kind = BC_STRJOIN;
		return read_uint16(bcr, &res->data.strjoin_nstrs);

	case INT_ADD: res->kind = BC_INT_ADD; return true;
	case INT_SUB: res->kind = BC_INT_SUB; return true;
	case INT_NEG: res->kind = BC_INT_NEG; return true;
	case INT_MUL: res->kind = BC_INT_MUL; return true;

	default:
		interp_errstr_printf(bcr->interp, "unknown op byte");
		append_byte_2_errstr(bcr->interp, opbyte);
		return false;
	}
}

// this is for a temporary linked list of BcOps
struct Link {
	struct BcOp op;
	struct Link *prev;
};

static bool read_body(struct BcReader *bcr, struct Bc *bc)
{
	if (!read_uint16(bcr, &bc->nlocalvars))
		return false;

	struct Link *last = NULL;
	bc->nops = 0;

	while(true) {
		unsigned char ob;
		if (!read_opbyte(bcr, &ob))
			goto error;
		if (ob == END_OF_BODY)
			break;

		struct BcOp val;
		val.lineno = bcr->lineno;
		// val.kind and val.data must be set in read_op()

		if (!read_op(bcr, ob, &val))
			goto error;

		struct Link *lnk = malloc(sizeof *lnk);
		if (!lnk) {
			bcop_destroy(&val);
			interp_errstr_nomem(bcr->interp);
			goto error;
		}

		lnk->op = val;
		lnk->prev = last;
		last = lnk;
		bc->nops++;
	}

	if(!( bc->ops = malloc(sizeof(struct BcOp) * bc->nops) )) {
		interp_errstr_nomem(bcr->interp);
		goto error;
	}

	size_t i = bc->nops;
	for (struct Link *lnk = last, *prev; lnk; lnk = prev) {
		prev = lnk->prev;
		bc->ops[--i] = lnk->op;
		free(lnk);
	}
	return true;

error:
	for (struct Link *lnk = last, *prev; lnk; lnk = prev) {
		prev = lnk->prev;
		bcop_destroy(&lnk->op);
		free(lnk);
	}
	return false;
}

bool bcreader_readcodepart(struct BcReader *bcr, struct Bc *bc)
{
	// TODO: check byte after body
	return read_body(bcr, bc);
}
