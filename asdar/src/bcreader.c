#include "bcreader.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "builtin.h"
#include "code.h"
#include "dynarray.h"
#include "interp.h"
#include "object.h"
#include "path.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/int.h"
#include "objects/string.h"

#define SET_LINENO 'L'
#define GET_BUILTIN_VAR 'U'
#define STR_CONSTANT '"'
#define CALL_BUILTIN_FUNCTION 'b'
#define CALL_THIS_FILE_FUNCTION '('
#define JUMP 'K'
#define JUMP_IF 'J'
#define STRING_JOIN 'j'
#define NON_NEGATIVE_INT_CONSTANT '1'
#define NEGATIVE_INT_CONSTANT '2'
#define THROW 't'
#define RETURN 'r'
#define POP 'P'
#define SWAP 'S'
#define DUP 'D'

//#define DEBUG(...) printf(__VA_ARGS__)
#define DEBUG(...) (void)0


struct BcReader {
	Interp *interp;
	FILE *file;
	uint32_t lineno;
	const char *bcpathabs;
	size_t modidx;
};


static bool read_bytes(struct BcReader *bcr, unsigned char *buf, size_t n)
{
	if (fread(buf, 1, n, bcr->file) == n)
		return true;

	// TODO: include file name file error msg?
	if (feof(bcr->file))   // feof does not set errno
		errobj_set_oserr(bcr->interp, "unexpected end of file");
	else
		errobj_set_oserr(bcr->interp, "reading '%s' failed", bcr->bcpathabs);
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

CREATE_UINT_READER(16)
CREATE_UINT_READER(32)

#undef CREATE_UINT_READER


static bool read_string(struct BcReader *bcr, char **str, uint32_t *len)
{
	if (!read_uint32(bcr, len))
		return false;

	// len+1 so that adding 0 byte will be easy if needed, and empty string is not a special case
	if (!( *str = malloc((*len) + 1) )) {
		*len = 0;
		errobj_set_nomem(bcr->interp);
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
		// TODO: maybe a separate error type for bytecode errors?
		errobj_set(bcr->interp, &errtype_value, "unexpected 0 byte file string");
		free(*str);
		return false;
	}
	return true;
}

static bool read_path(struct BcReader *bcr, char **resptr)
{
	// "foo" --> "/some/path/blah.asdac/../foo" --> "/some/path/foo"

	char *path;
	if (!read_string0(bcr, &path))
		return false;

	*resptr = path_concat(
		(const char*[]){ bcr->bcpathabs, path, NULL },
		PATH_FIRSTPARENT | PATH_RMDOTDOT_DUMB);

	if (!*resptr) {
		printf("%s\n", bcr->interp->basedir);
		errobj_set_oserr(bcr->interp, "cannot create absolute path of '%s'", path);
	}
	free(path);
	return !!*resptr;
}

bool read_asda_bytes(struct BcReader *bcr)
{
	static const unsigned char asda[] = { 'a', 's', 'd', 'a', 0xA5, 0xDA };

	unsigned char buf[sizeof asda];
	if (!read_bytes(bcr, buf, sizeof buf))
		return false;

	if (memcmp(buf, asda, sizeof asda) == 0)
		return true;
	errobj_set(bcr->interp, &errtype_value, "the file doesn't seem to be a compiled asda file");
	return false;
}

static bool read_opbyte(struct BcReader *bcr, unsigned char *ob)
{
	if (!read_bytes(bcr, ob, 1)) return false;
	if (*ob == SET_LINENO) {
		if (!read_uint32(bcr, &bcr->lineno)) return false;
		if (!read_bytes(bcr, ob, 1)) return false;
		if (*ob == SET_LINENO) {
			errobj_set(bcr->interp, &errtype_value, "repeated lineno byte: %B", SET_LINENO);
			return false;
		}
	}
	return true;
}

static bool read_get_builtin_var(struct BcReader *bcr, struct CodeOp *res)
{
	uint8_t i;
	if (!read_bytes(bcr, &i, 1))
		return false;

	switch(i) {
	// FIXME: dis is stupid shit switch shit
	case 0:
		res->data.obj = (Object *) &boolobj_true;
		break;
	case 1:
		res->data.obj = (Object *) &boolobj_false;
		break;
	default:
		printf("wat %d\n", (int)i);
		assert(0);
		break;
	}

	res->kind = CODE_CONSTANT;
	OBJECT_INCREF(res->data.obj);
	return true;
}

static bool read_string_constant(struct BcReader *bcr, Object **objptr)
{
	char *str;
	uint32_t len;
	if (!read_string(bcr, &str, &len))
		return false;

	*objptr = (Object *)stringobj_new_utf8(bcr->interp, str, len);
	free(str);
	return !!*objptr;
}

static bool read_int_constant(struct BcReader *bcr, Object **objptr, bool negate)
{
	// TODO: use read_string()
	uint32_t len;
	if(!read_uint32(bcr, &len))
		return false;

	unsigned char *buf = malloc(len);
	if(!buf) {
		errobj_set_nomem(bcr->interp);
		return false;
	}

	if(!read_bytes(bcr, buf, len)) {
		free(buf);
		return false;
	}

	*objptr = (Object *)intobj_new_lebytes(bcr->interp, buf, len, negate);
	free(buf);
	return !!*objptr;
}

static bool read_jump(struct BcReader *bcr, size_t *res, size_t jumpstart)
{
	uint16_t offset;
	if (!read_uint16(bcr, &offset))
		return false;

	*res = jumpstart + (size_t)offset;
	return true;
}

static const struct BuiltinFunc *
read_builtin_func(struct BcReader *bcr)
{
	uint8_t i;
	if (!read_bytes(bcr, &i, 1))
		return NULL;
	return &builtin_funcs[i];
}

// TODO: when function begin, grow the stack to required size
static bool read_op(struct BcReader *bcr, unsigned char opbyte, struct CodeOp *res, size_t jumpstart)
{
	switch(opbyte) {
	case STR_CONSTANT:
		res->kind = CODE_CONSTANT;
		return read_string_constant(bcr, &res->data.obj);

	case GET_BUILTIN_VAR:
		return read_get_builtin_var(bcr, res);

	case CALL_THIS_FILE_FUNCTION:
		res->kind = CODE_CALLCODEFUNC;
		return read_jump(bcr, &res->data.call.jump, jumpstart)
			&& read_uint16(bcr, &res->data.call.nargs);   // TODO: is this necessary?

	case CALL_BUILTIN_FUNCTION:
		res->kind = CODE_CALLBUILTINFUNC;
		return !!( res->data.builtinfunc = read_builtin_func(bcr) );

	case JUMP:           res->kind = CODE_JUMP;         return read_jump(bcr, &res->data.jump, jumpstart);
	case JUMP_IF:        res->kind = CODE_JUMPIF;       return read_jump(bcr, &res->data.jump, jumpstart);

	case NON_NEGATIVE_INT_CONSTANT:
	case NEGATIVE_INT_CONSTANT:
		res->kind = CODE_CONSTANT;
		return read_int_constant(bcr, &res->data.obj, opbyte==NEGATIVE_INT_CONSTANT);

	case STRING_JOIN:
		res->kind = CODE_STRJOIN;
		return read_uint16(bcr, &res->data.strjoin_nstrs);

	case SWAP:
		res->kind = CODE_SWAP;
		return read_uint16(bcr, &res->data.swap.index1) &&
				read_uint16(bcr, &res->data.swap.index2);

	case DUP: res->kind = CODE_DUP; return read_uint16(bcr, &res->data.objstackidx);

	case RETURN:  res->kind = CODE_RETURN;  return true;
	case THROW:   res->kind = CODE_THROW;   return true;
	case POP:     res->kind = CODE_POP;     return true;

	default:
		errobj_set(bcr->interp, &errtype_value, "unknown op byte: %B", opbyte);
		return false;
	}
}

static bool read_function(struct BcReader *bcr, size_t jumpstart)
{
	uint16_t bodylen;
	if (!read_uint16(bcr, &bodylen))
		return false;

	DEBUG("  bodylen = %d\n", (int)bodylen);

	size_t oldlen = bcr->interp->code.len;
	if (!dynarray_alloc(bcr->interp, &bcr->interp->code, oldlen + bodylen))
		return false;

	uint16_t i;
	for (i = 0; i < bodylen; i++){
		unsigned char ob;
		if (!read_opbyte(bcr, &ob))
			goto error;

		struct CodeOp *op = &bcr->interp->code.ptr[oldlen + i];
		op->lineno = bcr->lineno;
		op->modidx = bcr->modidx;
		// data and kind are filled by read_op()

		if (!read_op(bcr, ob, op, jumpstart))
			goto error;
		DEBUG("    opbyte: ");
		//codeop_debug(op->kind);
	}

	bcr->interp->code.len = oldlen + bodylen;
	return true;

error:
	// let read_code_part() handle it all
	bcr->interp->code.len = oldlen + i;
	return false;
}

static long read_code_part(struct BcReader *bcr)
{
	size_t jumpstart = bcr->interp->code.len;

	uint16_t nfuncs;
	if (!read_uint16(bcr, &nfuncs))
		return false;
	assert(nfuncs >= 1);   // at least main
	DEBUG("nfuncs = %d\n", nfuncs);

	for (uint16_t i = 0; i < nfuncs; i++) {
		if (!read_function(bcr, jumpstart))
			goto error;
	}

	// main is first
	return (long)jumpstart;

error:
	while (bcr->interp->code.len > jumpstart)
		codeop_destroy(dynarray_pop(&bcr->interp->code));
	return -1;
}

bool bcreader_read(Interp *interp, char *bcpathrel)
{
	// make sure there's enough room for modinfo when cleaning up on error is easy
	size_t modidx = interp->mods.len;
	if (!dynarray_alloc(interp, &interp->mods, modidx + 1)) {
		free(bcpathrel);
		return false;
	}

	struct InterpModInfo *mod = &interp->mods.ptr[modidx];
	mod->bcpathrel = bcpathrel;
	mod->bcpathabs = NULL;
	mod->srcpathabs = NULL;

	if (!( mod->bcpathabs = path_concat((const char*[]){interp->basedir, bcpathrel, NULL}, 0) )) {
		errobj_set_oserr(interp, "cannot get absolute path of '%s'", bcpathrel);
		goto error;
	}

	struct BcReader bcr = {
		.interp = interp,
		.lineno = 1,
		.bcpathabs = mod->bcpathabs,
		.modidx = modidx,
	};

	if (!( bcr.file = fopen(mod->bcpathabs, "rb") )) {
		errobj_set_oserr(interp, "cannot open '%s'", mod->bcpathabs);
		goto error;
	}

	long startidx;
	bool ok =
		read_asda_bytes(&bcr) &&
		read_path(&bcr, &mod->srcpathabs) &&
		(startidx = read_code_part(&bcr)) != -1;
	fclose(bcr.file);
	if (!ok)
		goto error;

	mod->startidx = (size_t)startidx;
	interp->mods.len++;
	return true;

error:
	free(mod->bcpathrel);
	free(mod->bcpathabs);
	free(mod->srcpathabs);
	return false;
}
