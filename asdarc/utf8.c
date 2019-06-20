#include "utf8.h"
#include <assert.h>
#include <stdarg.h>
#include <stdbool.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include "interp.h"

// reference: https://en.wikipedia.org/wiki/UTF-8


static int how_many_bytes(struct Interp *interp, uint32_t codepnt)
{
	if (codepnt <= 0x7f)
		return 1;
	if (codepnt <= 0x7ff)
		return 2;
	if (codepnt <= 0xffff) {
		if (0xd800 <= codepnt && codepnt <= 0xdfff)
			goto invalid_code_point;
		return 3;
	}
	if (codepnt <= 0x10ffff)
		return 4;

	// "fall through" to invalid_code_point

invalid_code_point:
	sprintf(interp->errstr, "invalid Unicode code point %04lu", (unsigned long)codepnt);
	return -1;
}


// example: ONES(6) is 111111 in binary
#define ONES(n) ((1<<(n))-1)

bool utf8_encode(
	struct Interp *interp,
	const uint32_t *unicode, size_t unicodelen,
	char **utf8, size_t *utf8len)
{
	// don't set utf8len if this fails
	size_t utf8len_val = 0;
	for (const uint32_t *p = unicode; p < unicode + unicodelen; p++) {
		int part = how_many_bytes(interp, *p);
		if (part < 0)
			return false;
		utf8len_val += (size_t)part;
	}

	unsigned char *ptr = malloc(utf8len_val+1);
	if (!ptr) {
		sprintf(interp->errstr, "not enough memory");
		return false;
	}

	// rest of this will not fail
	*utf8 = (char *)ptr;
	*utf8len = utf8len_val;

	for (; unicodelen; (unicode++, unicodelen--)) {
		// how_many_bytes can't fail anymore
		switch (how_many_bytes(NULL, *unicode)) {
		case 1:
			*ptr++ = (unsigned char) *unicode;
			break;
		case 2:
			*ptr++ = (unsigned char)( ONES(2)<<6 | *unicode>>6 );
			*ptr++ = (unsigned char)( 1<<7 | (*unicode & ONES(6)) );
			break;
		case 3:
			*ptr++ = (unsigned char)( ONES(3)<<5 | *unicode>>12 );
			*ptr++ = (unsigned char)( 1<<7 | (*unicode>>6 & ONES(6)) );
			*ptr++ = (unsigned char)( 1<<7 | (*unicode & ONES(6)) );
			break;
		case 4:
			*ptr++ = (unsigned char)( ONES(4)<<4 | *unicode>>18 );
			*ptr++ = (unsigned char)( 1<<7 | (*unicode>>12 & ONES(6)) );
			*ptr++ = (unsigned char)( 1<<7 | (*unicode>>6 & ONES(6)) );
			*ptr++ = (unsigned char)( 1<<7 | (*unicode & ONES(6)) );
			break;
		default:
			assert(0);
		}
	}
	return true;
}


static int decode_character(struct Interp *interp, const unsigned char *uutf8, size_t utf8len, uint32_t *ptr)
{
#define CHECK_UTF8LEN(n)      do{ if (utf8len < (size_t)(n)) { sprintf(interp->errstr, "unexpected end of string");           return -1; }}while(0)
#define CHECK_CONTINUATION(c) do{ if ((c)>>6 != 1<<1)        { sprintf(interp->errstr, "invalid continuation byte %#x", (c)); return -1; }}while(0)
	if (uutf8[0] >> 7 == 0) {
		CHECK_UTF8LEN(1);
		*ptr = uutf8[0];
		return 1;
	}

	if (uutf8[0] >> 5 == ONES(2) << 1) {
		CHECK_UTF8LEN(2);
		CHECK_CONTINUATION(uutf8[1]);
		*ptr =
			(uint32_t)(ONES(5) & uutf8[0])<<UINT32_C(6) |
			(uint32_t)(ONES(6) & uutf8[1]);
		return 2;
	}

	if (uutf8[0] >> 4 == ONES(3) << 1) {
		CHECK_UTF8LEN(3);
		CHECK_CONTINUATION(uutf8[1]);
		CHECK_CONTINUATION(uutf8[2]);
		*ptr =
			((uint32_t)(ONES(4) & uutf8[0]))<<UINT32_C(12) |
			((uint32_t)(ONES(6) & uutf8[1]))<<UINT32_C(6) |
			((uint32_t)(ONES(6) & uutf8[2]));
		return 3;
	}

	else if (uutf8[0] >> 3 == ONES(4) << 1) {
		CHECK_UTF8LEN(4);
		CHECK_CONTINUATION(uutf8[1]);
		CHECK_CONTINUATION(uutf8[2]);
		CHECK_CONTINUATION(uutf8[3]);
		*ptr =
			((uint32_t)(ONES(3) & uutf8[0]))<<UINT32_C(18) |
			((uint32_t)(ONES(6) & uutf8[1]))<<UINT32_C(12) |
			((uint32_t)(ONES(6) & uutf8[2]))<<UINT32_C(6) |
			((uint32_t)(ONES(6) & uutf8[3]));
		return 4;
	}
#undef CHECK_UTF8LEN
#undef CHECK_CONTINUATION

	sprintf(interp->errstr, "invalid start byte %#x", (int) uutf8[0]);
	return -1;
}

bool utf8_decode(
	struct Interp *interp,
	const char *utf8, size_t utf8len,
	uint32_t **unicode, size_t *unicodelen)
{
	if (utf8len == 0) {
		*unicodelen = 0;
		*unicode = NULL;
		return true;
	}

	// must leave unicode and unicodelen untouched on error
	uint32_t *result;
	size_t resultlen = 0;

	// each utf8 byte is at most 1 unicode code point
	// this is realloc'd later to the correct size, feels better than many reallocs
	if (!(result = malloc((utf8len+1)*sizeof(uint32_t)))) {
		sprintf(interp->errstr, "not enough memory");
		return false;
	}

	// if this isn't guaranteed to work, then it's a corner case that doesn't
	// happen on any computer that this code will run on
	const unsigned char *uutf8 = (const unsigned char*)utf8;

	while (utf8len > 0) {
		int nbytes, expected_nbytes;
		if( (nbytes = decode_character(interp, uutf8, utf8len, &result[resultlen])) == -1 ) goto error;
		if( (expected_nbytes = how_many_bytes(interp, result[resultlen])) == -1 ) goto error;

		// utf8 works so that when there would otherwise be multiple ways to encode
		// something, only the shortest one is ok
		assert(!(nbytes < expected_nbytes));    // it can't fit in that little space
		if (nbytes > expected_nbytes) {
			// overlong encoding
			if (nbytes == 2)
				sprintf(interp->errstr, "overlong encoding: %#x %#x", (int) uutf8[0], (int) uutf8[1]);
			else if (nbytes == 3)
				sprintf(interp->errstr, "overlong encoding: %#x %#x %#x", (int) uutf8[0], (int) uutf8[1], (int) uutf8[2]);
			else if (nbytes == 4)
				sprintf(interp->errstr, "overlong encoding: %#x %#x %#x %#x", (int) uutf8[0], (int) uutf8[1], (int) uutf8[2], (int) uutf8[3]);
			else
				assert(0);
			goto error;
		}

		resultlen += 1;
		uutf8 += nbytes;
		utf8len -= (unsigned)nbytes;
	}

	// this realloc can't fail because it frees memory, never allocates more
	*unicode = realloc(result, (resultlen+1)*sizeof(uint32_t));
	assert(*unicode);
	*unicodelen = resultlen;
	return true;

error:
	if (result)
		free(result);
	return false;
}
