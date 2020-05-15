#include <assert.h>
#include <stdbool.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <src/utf8.h>
#include <src/objects/err.h>
#include "util.h"

// what should the encode or decode test do with this example?
enum What2Do { SUCCEED, FAIL, SKIP };

struct Utf8Example {
	unsigned char utf8[20];   // easier to write the test bytes as unsigned
	size_t utf8len;
	uint32_t uni[20];
	size_t unilen;
	char errstr[100];
	enum What2Do encodew2d;
	enum What2Do decodew2d;
};

static const struct Utf8Example examples[] = {
	{ {0}, 0, {0}, 0, "", SUCCEED, SUCCEED },
	{ {'h','e','l','l','o'}, 5, {'h','e','l','l','o'}, 5, "", SUCCEED, SUCCEED },

	// 0 byte is not special
	{ {'h','e','l','l',0,'o'}, 6, {'h','e','l','l',0,'o'}, 6, "", SUCCEED, SUCCEED },

	// 1, 2, 3 and 4 byte unicode characters
	{
		{0x64, 0xcf,0xa8, 0xe0,0xae,0xb8, 0xf0,0x90,0x85,0x83}, 1+2+3+4,
		{100,1000,3000,0x10143UL}, 4,
		"", SUCCEED, SUCCEED,
	},

	// finnish text
	{
		{0xc3,0xa4, 0xc3,0xa4, 'k','k', 0xc3,0xb6, 's','e','t'}, 2+2+1+1+2+1+1+1,
		{0xe4, 0xe4, 'k', 'k', 0xf6, 's', 'e', 't'}, 8,
		"", SUCCEED, SUCCEED,
	},

	// euro sign
	{ {0xe2,0x82,0xac}, 3, {0x20ac}, 1, "", SUCCEED, SUCCEED },

	// euro sign with overlong encoding, from wikipedia
	{ {0xf0,0x82,0x82,0xac}, 4, {0}, 0, "overlong encoding: 0xf0, 0x82, 0x82, 0xac", SKIP, FAIL },

	// euro sign with first byte missing, unexpected continuation byte, non-overlong and overlong
	{ {0x82,0xac}, 2, {0}, 0, "invalid start byte: 0x82", SKIP, FAIL },
	{ {0x82,0x82,0xac}, 3, {0}, 0, "invalid start byte: 0x82", SKIP, FAIL },

	// euro sign with last byte missing, non-overlong and overlong
	{ {0xe2,0x82}, 2, {0}, 0, "unexpected end of string", SKIP, FAIL },
	{ {0xf0,0x82,0x82}, 3, {0}, 0, "unexpected end of string", SKIP, FAIL },

	// code points from U+D800 to U+DFFF are invalid
	{ {0xed, 0x9f, 0xbf}, 3, {0xd7ffU}, 1, "", SUCCEED, SUCCEED },
	{ {0xed, 0xa0, 0x80}, 3, {0xd800U}, 1, "invalid Unicode code point U+D800", FAIL, FAIL },
	{ {0xed, 0xa0, 0x81}, 3, {0xd801U}, 1, "invalid Unicode code point U+D801", FAIL, FAIL },
	{ {0xed, 0xbf, 0xbe}, 3, {0xdffeU}, 1, "invalid Unicode code point U+DFFE", FAIL, FAIL },
	{ {0xed, 0xbf, 0xbf}, 3, {0xdfffU}, 1, "invalid Unicode code point U+DFFF", FAIL, FAIL },
	{ {0xee, 0x80, 0x80}, 3, {0xe000U}, 1, "", SUCCEED, SUCCEED },
};

TEST(utf8_encode)
{
	for (size_t i = 0; i < sizeof(examples)/sizeof(examples[0]); i++) {
		const struct Utf8Example ex = examples[i];
		if (ex.encodew2d == SKIP)
			continue;

		char *utf8;
		size_t utf8len;
		bool ok = utf8_encode(interp, ex.uni, ex.unilen, &utf8, &utf8len);

		switch(ex.encodew2d) {
		case SUCCEED:
			assert(ok);
			assert(utf8len == ex.utf8len);
			assert(memcmp(ex.utf8, utf8, utf8len) == 0);
			assert(utf8[utf8len] == 0);
			free(utf8);
			break;
		case FAIL:
			assert(!ok);
			assert_error_matches_and_clear(interp, &errtype_value, ex.errstr);
			break;
		case SKIP:
			assert(0);
		}
	}
}

TEST(utf8_validate)
{
	for (size_t i = 0; i < sizeof(examples)/sizeof(examples[0]); i++) {
		const struct Utf8Example ex = examples[i];

		switch(ex.decodew2d) {
		case SUCCEED:
			assert(utf8_validate(NULL, (const char *)ex.utf8, ex.utf8len));
			assert(utf8_validate(interp, (const char *)ex.utf8, ex.utf8len));
			assert(!interp->err);
			break;
		case FAIL:
			assert(!utf8_validate(NULL, (const char *)ex.utf8, ex.utf8len));
			assert(!interp->err);
			assert(!utf8_validate(interp, (const char *)ex.utf8, ex.utf8len));
			assert_error_matches_and_clear(interp, &errtype_value, ex.errstr);
			break;
		case SKIP:
			break;
		}
	}
}

TEST(utf8_decode)
{
	for (size_t i = 0; i < sizeof(examples)/sizeof(examples[0]); i++) {
		const struct Utf8Example ex = examples[i];
		if (ex.decodew2d != SUCCEED)
			continue;

		uint32_t *uni;
		size_t unilen;
		bool ok = utf8_decode(interp, (const char *)ex.utf8, ex.utf8len, &uni, &unilen);
		assert(ok);
		assert(unilen == ex.unilen);

		// memcmp will do the right thing because uint32_t exists and CHAR_BIT == 8
		// if those assumptions aren't true, then your platform is unsupported, sorry
		assert(memcmp(uni, ex.uni, unilen * sizeof(uint32_t)) == 0);
		free(uni);
	}
}
