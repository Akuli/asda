#include "bcreader.h"
#include <assert.h>
#include <stdbool.h>
#include <stdlib.h>
#include <string.h>
#include "code.h"
#include "builtin.h"
#include "module.h"
#include "objtyp.h"
#include "path.h"
#include "objects/bool.h"
#include "objects/func.h"
#include "objects/int.h"
#include "objects/scope.h"
#include "objects/string.h"

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
#define POP_ONE 'P'
#define JUMPIF 'J'
#define STRING_JOIN 'j'
#define GET_METHOD '.'   // currently all attributes are methods
#define GET_FROM_MODULE 'm'
#define NON_NEGATIVE_INT_CONSTANT '1'
#define NEGATIVE_INT_CONSTANT '2'
#define INT_ADD '+'
#define INT_SUB '-'
#define INT_NEG '_'
#define INT_MUL '*'
#define CREATE_FUNCTION 'f'
#define VOID_RETURN 'r'
#define VALUE_RETURN 'R'
#define DIDNT_RETURN_ERROR 'd'
#define END_OF_BODY 'E'

#define TYPEBYTE_BUILTIN 'b'
#define TYPEBYTE_FUNC 'f'
#define TYPEBYTE_VOID 'v'

// from the tables in ascii(7), we see that '!' is first printable ascii char and '~' is last
#define is_printable_ascii(c) ('!' <= (c) && (c) <= '~')


struct BcReader bcreader_new(Interp *interp, FILE *in, const char *indirname)
{
	struct BcReader res;
	res.interp = interp;
	res.in = in;
	res.indirname = indirname;
	res.lineno = 1;

	// for bcreader_destroy
	res.imports = NULL;
	res.nimports = 0;

	return res;
}

void bcreader_destroy(const struct BcReader *bcr)
{
	for (size_t i = 0; i < bcr->nimports; i++)
		free(bcr->imports[i]);
	free(bcr->imports);
}


static bool read_bytes(struct BcReader *bcr, unsigned char *buf, size_t n)
{
	if (fread(buf, 1, n, bcr->in) == n)
		return true;

	if (feof(bcr->in))
		interp_errstr_printf(bcr->interp, "unexpected end of file");
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
	free(path);
	if (!*resptr) {
		interp_errstr_printf_errno(bcr->interp, "cannot create absolute path of '%s'", path);
		return false;
	}
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

bool bcreader_readimports(struct BcReader *bcr)
{
	unsigned char b;
	if (!read_bytes(bcr, &b, 1))
		goto error;
	if (b != IMPORT_SECTION) {
		interp_errstr_printf(bcr->interp, "expected import section, got %#x", (int)b);
		goto error;
	}

	uint16_t tmp;
	if (!read_uint16(bcr, &tmp))
		goto error;
	bcr->nimports = tmp;

	if (bcr->nimports == 0)
		return true;

	if (!( bcr->imports = malloc(sizeof(char*) * bcr->nimports) )) {
		interp_errstr_nomem(bcr->interp);
		goto error;
	}

	for (size_t i=0; i < bcr->nimports; i++)
		if (!read_path(bcr, bcr->imports + i)) {
			for (size_t j=0; j<i; j++)
				free(bcr->imports[j]);
			free(bcr->imports);
			goto error;
		}

	return true;

error:
	bcr->imports = NULL;
	bcr->nimports = 0;
	return false;
}


static void append_byte_2_errstr(Interp *interp, unsigned char byte)
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

		interp_errstr_printf(bcr->interp, "unexpected void type byte");
		append_byte_2_errstr(bcr->interp, byte);
		return false;

	case TYPEBYTE_FUNC:
	{
		// TODO: this throws away most of the information, should it be used somewhere instead?
		const struct Type *rettyp;
		if(!read_type(bcr, &rettyp, true))
			return false;

		uint8_t nargs;
		if(!read_bytes(bcr, &nargs, 1))
			return false;
		for (uint8_t i = 0; i < nargs; i++) {
			const struct Type *ignored;
			if(!read_type(bcr, &ignored, false))
				return false;
		}

		*typ = rettyp ? &funcobj_type_ret : &funcobj_type_noret;
		return true;
	}

	default:
		interp_errstr_printf(bcr->interp, "unknown type byte");
		append_byte_2_errstr(bcr->interp, byte);
		return false;
	}
}

static bool read_vardata(struct BcReader *bcr, struct CodeOp *res, enum CodeOpKind kind)
{
	struct CodeVarData vd;
	if (!read_bytes(bcr, &vd.level, 1)) return false;
	if (!read_uint16(bcr, &vd.index)) return false;

	res->data.var = vd;
	res->kind = kind;
	return true;
}

static bool read_callfunc(struct BcReader *bcr, struct CodeOp *res, enum CodeOpKind kind)
{
	res->kind = kind;
	return read_bytes(bcr, &res->data.callfunc_nargs, 1);
}

static bool read_string_constant(struct BcReader *bcr, Object **objptr)
{
	char *str;
	uint32_t len;
	if (!read_string(bcr, &str, &len))
		return false;

	*objptr = stringobj_new_utf8(bcr->interp, str, len);
	free(str);
	return !!*objptr;
}

static bool read_int_constant(struct BcReader *bcr, Object **objptr, bool negate)
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


static bool read_body(struct BcReader *bcr, struct Code *code);  // forward declare
static bool read_create_function(struct BcReader *bcr, struct CodeOp *res)
{
	res->kind = CODE_CREATEFUNC;

	if (ungetc(TYPEBYTE_FUNC, bcr->in) == EOF) {
		interp_errstr_printf_errno(bcr->interp, "ungetc failed");
		return false;
	}

	const struct Type *functyp;
	if(!read_type(bcr, &functyp, false))
		return false;

	assert(functyp == &funcobj_type_ret || functyp == &funcobj_type_noret);
	res->data.createfunc.returning = (functyp == &funcobj_type_ret);

	unsigned char yieldbyt;
	if(!read_bytes(bcr, &yieldbyt, 1))
		return false;
	assert(yieldbyt == 0);   // TODO: support yielding

	return read_body(bcr, &res->data.createfunc.body);
}

static Object **get_module_member_pointer(struct BcReader *bcr)
{
	uint16_t modidx, membidx;
	if (!read_uint16(bcr, &modidx))
		return NULL;
	if (!read_uint16(bcr, &membidx))
		return NULL;

	// the module has been imported already when this runs
	// TODO: call module_get less times?
	const struct Module *mod = module_get(bcr->interp, bcr->imports[modidx]);
	assert(mod);
	return scopeobj_getlocalvarsptr(mod->scope) + membidx;
}

static bool read_op(struct BcReader *bcr, unsigned char opbyte, struct CodeOp *res)
{
	switch(opbyte) {
	case STR_CONSTANT:
		res->kind = CODE_CONSTANT;
		return read_string_constant(bcr, &res->data.obj);

	case TRUE_CONSTANT:
	case FALSE_CONSTANT:
		res->kind = CODE_CONSTANT;
		res->data.obj = boolobj_c2asda(opbyte == TRUE_CONSTANT);
		return true;

	case SET_VAR:
		return read_vardata(bcr, res, CODE_SETVAR);
	case GET_VAR:
		return read_vardata(bcr, res, CODE_GETVAR);
	case CALL_VOID_FUNCTION:
		return read_callfunc(bcr, res, CODE_CALLVOIDFUNC);
	case CALL_RETURNING_FUNCTION:
		return read_callfunc(bcr, res, CODE_CALLRETFUNC);
	case JUMPIF:
		res->kind = CODE_JUMPIF;
		return read_uint16(bcr, &res->data.jump_idx);
	case NON_NEGATIVE_INT_CONSTANT:
	case NEGATIVE_INT_CONSTANT:
		res->kind = CODE_CONSTANT;
		return read_int_constant(bcr, &res->data.obj, opbyte==NEGATIVE_INT_CONSTANT);
	case GET_METHOD:
		res->kind = CODE_GETMETHOD;
		if(!read_type(bcr, &res->data.lookupmethod.type, false))
			return false;
		if (!read_uint16(bcr, &res->data.lookupmethod.index))
			return false;
		assert(res->data.lookupmethod.index < res->data.lookupmethod.type->nmethods);
		return true;

	case GET_FROM_MODULE:
		res->kind = CODE_GETFROMMODULE;
		return !!( res->data.modmemberptr = get_module_member_pointer(bcr) );

	case CREATE_FUNCTION:
		return read_create_function(bcr, res);

	case STRING_JOIN:
		res->kind = CODE_STRJOIN;
		return read_uint16(bcr, &res->data.strjoin_nstrs);

	case BOOLNEG: res->kind = CODE_BOOLNEG; return true;
	case POP_ONE: res->kind = CODE_POP1; return true;

	case VOID_RETURN: res->kind = CODE_VOIDRETURN; return true;
	case VALUE_RETURN: res->kind = CODE_VALUERETURN; return true;
	case DIDNT_RETURN_ERROR: res->kind = CODE_DIDNTRETURNERROR; return true;

	case INT_ADD: res->kind = CODE_INT_ADD; return true;
	case INT_SUB: res->kind = CODE_INT_SUB; return true;
	case INT_NEG: res->kind = CODE_INT_NEG; return true;
	case INT_MUL: res->kind = CODE_INT_MUL; return true;

	default:
		interp_errstr_printf(bcr->interp, "unknown op byte");
		append_byte_2_errstr(bcr->interp, opbyte);
		return false;
	}
}

// this is for a temporary linked list of CodeOps
struct Link {
	struct CodeOp op;
	struct Link *prev;
};

static bool read_body(struct BcReader *bcr, struct Code *code)
{
	if (!read_uint16(bcr, &code->nlocalvars))
		return false;

	struct Link *last = NULL;
	code->nops = 0;

	while(true) {
		unsigned char ob;
		if (!read_opbyte(bcr, &ob))
			goto error;
		if (ob == END_OF_BODY)
			break;

		struct CodeOp val;
		val.lineno = bcr->lineno;
		// val.kind and val.data must be set in read_op()

		if (!read_op(bcr, ob, &val))
			goto error;

		struct Link *lnk = malloc(sizeof *lnk);
		if (!lnk) {
			codeop_destroy(&val);
			interp_errstr_nomem(bcr->interp);
			goto error;
		}

		lnk->op = val;
		lnk->prev = last;
		last = lnk;
		code->nops++;
	}

	if(!( code->ops = malloc(sizeof(struct CodeOp) * code->nops) )) {
		interp_errstr_nomem(bcr->interp);
		goto error;
	}

	size_t i = code->nops;
	for (struct Link *lnk = last, *prev; lnk; lnk = prev) {
		prev = lnk->prev;
		code->ops[--i] = lnk->op;
		free(lnk);
	}
	return true;

error:
	for (struct Link *lnk = last, *prev; lnk; lnk = prev) {
		prev = lnk->prev;
		codeop_destroy(&lnk->op);
		free(lnk);
	}
	return false;
}

bool bcreader_readcodepart(struct BcReader *bcr, struct Code *code)
{
	// TODO: check byte after body
	return read_body(bcr, code);
}
