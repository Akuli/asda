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
#include "type.h"
#include "objects/bool.h"
#include "objects/err.h"
#include "objects/int.h"
#include "objects/string.h"

#define TYPE_LIST_SECTION 'y'

#define SET_LINENO 'L'
#define GET_BUILTIN_VAR 'U'
#define CREATE_BOX '0'
#define SET_TO_BOX 'O'
#define UNBOX 'o'
#define SET_ATTR ':'
#define GET_ATTR '.'
#define STR_CONSTANT '"'
#define FUNCTION_BEGINS 'f'
#define CALL_BUILTIN_FUNCTION 'b'
#define CALL_THIS_FILE_FUNCTION '('
#define CALL_CONSTRUCTOR ')'
#define JUMP 'K'
#define JUMP_IF 'J'
#define JUMP_IF_EQ_INT '='
#define JUMP_IF_EQ_STR 'q'
#define STRING_JOIN 'j'
#define NON_NEGATIVE_INT_CONSTANT '1'
#define NEGATIVE_INT_CONSTANT '2'
#define THROW 't'
#define RETURN 'r'

#define POP 'P'
#define SWAP 'S'
#define DUP 'D'

#define INT_ADD '+'
#define INT_SUB '-'
#define INT_NEG '_'
#define INT_MUL '*'

#define TYPEBYTE_ASDACLASS 'a'
#define TYPEBYTE_BUILTIN 'b'
#define TYPEBYTE_VOID 'v'

#define DEBUG(...) printf(__VA_ARGS__)


struct BcReader bcreader_new(Interp *interp, FILE *in, const char *indirname)
{
	struct BcReader res = {0};  // most things to 0 for bcreader_destroy() and stuff
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

	// TODO: include file name in error msg?
	if (feof(bcr->in))   // feof does not set errno
		errobj_set_oserr(bcr->interp, "unexpected end of file");
	else
		errobj_set_oserr(bcr->interp, "reading failed");
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
	if (!( *str = malloc((*len)+1) )) {
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
		errobj_set(bcr->interp, &errobj_type_value, "unexpected 0 byte in string");
		free(*str);
		return false;
	}
	return true;
}

static bool read_path(struct BcReader *bcr, char **resptr)
{
	char *path;
	if (!read_string0(bcr, &path))
		return false;

	// compiler lowercases all the paths, that's not needed here

	if (PATH_SLASH != '/') {
		char *p = path;
		while (( p = strchr(p, '/') ))
			*p++ = PATH_SLASH;
	}

	*resptr = path_concat_dotdot(bcr->indirname, path);
	if (!*resptr)
		errobj_set_oserr(bcr->interp, "cannot create absolute path of '%s'", path);
	free(path);
	return !!*resptr;
}


static const unsigned char asda[6] = { 'a', 's', 'd', 'a', 0xA5, 0xDA };

bool bcreader_readasdabytes(struct BcReader *bcr)
{
	unsigned char buf[sizeof asda];
	if (!read_bytes(bcr, buf, sizeof buf))
		return false;

	if (memcmp(buf, asda, sizeof asda) == 0)
		return true;
	errobj_set(bcr->interp, &errobj_type_value, "the file doesn't seem to be a compiled asda file");
	return false;
}

bool bcreader_readsourcepath(struct BcReader *bcr)
{
	char *res;
	if (!read_path(bcr, &res))
		return NULL;
	bcr->srcpath = res;
	return true;
}

static bool read_type(struct BcReader *bcr, const struct Type **typ, bool allowvoid)
{
	unsigned char byte;
	if(!read_bytes(bcr, &byte, 1))
		return false;

	switch(byte) {
	case TYPEBYTE_BUILTIN:
	{
		uint8_t i;
		if (!read_bytes(bcr, &i, 1))
			return false;
		assert(i < builtin_ntypes);
		*typ = builtin_types[i];
		return true;
	}

	case TYPEBYTE_VOID:
		if (allowvoid) {
			*typ = NULL;
			return true;
		}

		errobj_set(bcr->interp, &errobj_type_value, "unexpected void type byte: %B", byte);
		return false;

	default:
		errobj_set(bcr->interp, &errobj_type_value, "unknown type byte: %B", byte);
		return false;
	}
}

// TODO: include types of constructor arguments everywhere, including non-asdaclass types?
static struct TypeAsdaClass *read_asda_class_type(struct BcReader *bcr)
{
	uint16_t nasdaattribs, nmethods;
	if (!read_uint16(bcr, &nasdaattribs) ||
		!read_uint16(bcr, &nmethods))
	{
		return NULL;
	}

	return type_asdaclass_new(bcr->interp, nasdaattribs, nmethods);
}

static bool read_opbyte(struct BcReader *bcr, unsigned char *ob)
{
	if (!read_bytes(bcr, ob, 1)) return false;
	if (*ob == SET_LINENO) {
		if (!read_uint32(bcr, &bcr->lineno)) return false;
		if (!read_bytes(bcr, ob, 1)) return false;
		if (*ob == SET_LINENO) {
			errobj_set(bcr->interp, &errobj_type_value, "repeated lineno byte: %B", SET_LINENO);
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

static bool read_attribute(struct BcReader *bcr, struct CodeOp *res) {
	if(!read_type(bcr, &res->data.attr.type, false))
		return false;
	if (!read_uint16(bcr, &res->data.attr.index))
		return false;

	assert(res->data.attr.index < res->data.attr.type->nattrs);
	return true;
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

static bool read_op(struct BcReader *bcr, unsigned char opbyte, struct CodeOp *res, size_t jumpstart)
{
	switch(opbyte) {
	case STR_CONSTANT:
		res->kind = CODE_CONSTANT;
		return read_string_constant(bcr, &res->data.obj);

	case GET_BUILTIN_VAR:
		return read_get_builtin_var(bcr, res);

	// TODO: make the compiler emit info about stack sizes again
	case FUNCTION_BEGINS: res->kind = CODE_FUNCBEGINS; return read_uint16(bcr, &res->data.objstackincr);

	case CREATE_BOX: res->kind = CODE_CREATEBOX; return true;
	case SET_TO_BOX: res->kind = CODE_SET2BOX;   return true;
	case UNBOX:      res->kind = CODE_UNBOX;     return true;

	case CALL_THIS_FILE_FUNCTION:
		res->kind = CODE_CALLCODEFUNC;
		return read_jump(bcr, &res->data.call.jump, jumpstart)
			&& read_uint16(bcr, &res->data.call.nargs);   // TODO: is this necessary?

	case CALL_BUILTIN_FUNCTION:
		res->kind = CODE_CALLBUILTINFUNC;
		return !!( res->data.builtinfunc = read_builtin_func(bcr) );

	case JUMP:           res->kind = CODE_JUMP;         return read_jump(bcr, &res->data.jump, jumpstart);
	case JUMP_IF:        res->kind = CODE_JUMPIF;       return read_jump(bcr, &res->data.jump, jumpstart);
	case JUMP_IF_EQ_INT: res->kind = CODE_JUMPIFEQ_INT; return read_jump(bcr, &res->data.jump, jumpstart);
	case JUMP_IF_EQ_STR: res->kind = CODE_JUMPIFEQ_STR; return read_jump(bcr, &res->data.jump, jumpstart);

	case NON_NEGATIVE_INT_CONSTANT:
	case NEGATIVE_INT_CONSTANT:
		res->kind = CODE_CONSTANT;
		return read_int_constant(bcr, &res->data.obj, opbyte==NEGATIVE_INT_CONSTANT);

	case GET_ATTR: res->kind = CODE_GETATTR; return read_attribute(bcr, res);
	case SET_ATTR:
		res->kind = CODE_SETATTR;
		return read_attribute(bcr, res);

	case STRING_JOIN:
		res->kind = CODE_STRJOIN;
		return read_uint16(bcr, &res->data.strjoin_nstrs);

	case SWAP:
		res->kind = CODE_SWAP;
		return read_uint16(bcr, &res->data.swap.index1) &&
				read_uint16(bcr, &res->data.swap.index2);

	case DUP: res->kind = CODE_DUP; return read_uint16(bcr, &res->data.objstackidx);

	case INT_ADD: res->kind = CODE_INT_ADD; return true;
	case INT_SUB: res->kind = CODE_INT_SUB; return true;
	case INT_NEG: res->kind = CODE_INT_NEG; return true;
	case INT_MUL: res->kind = CODE_INT_MUL; return true;
	case RETURN:  res->kind = CODE_RETURN;  return true;
	case POP:     res->kind = CODE_POP;     return true;

	default:
		errobj_set(bcr->interp, &errobj_type_value, "unknown op byte: %B", opbyte);
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
		op->srcpath = bcr->srcpath;
		// data and kind are filled by read_op()

		if (!read_op(bcr, ob, op, jumpstart))
			goto error;
		DEBUG("    opbyte: ");
		codeop_debug(op->kind);
	}

	bcr->interp->code.len = oldlen + bodylen;
	return true;

error:
	// let bcreader_readcodepart() handle it all
	bcr->interp->code.len = oldlen + i;
	return false;
}

long bcreader_readcodepart(struct BcReader *bcr)
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
