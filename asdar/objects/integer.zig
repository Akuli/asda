const std = @import("std");
const assert = std.debug.assert;
const Interp = @import("../interp.zig").Interp;
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;

use @cImport(@cInclude("gmp.h"));


var type_value = objtyp.Type.init([]*Object { });
pub const typ = &type_value;

pub const Data = struct {
    interp: *Interp,
    mpz: *mpz_t,

    pub fn destroy(self: Data, decref_refs: bool, free_nonrefs: bool) void {
        if (free_nonrefs) {
            mpz_clear(&self.mpz[0]);
            self.interp.object_allocator.destroy(self.mpz);
        }
    }
};

pub fn newFromFunnyAsdaBytecodeNumberString(interp: *Interp, s: []const u8, negative: bool) !*Object {
    var val = try interp.object_allocator.create(mpz_t);
    errdefer interp.object_allocator.destroy(val);

    mpz_init2(&val[0], s.len*8);    // val = 0
    for (s) |byte| {
        mpz_mul_2exp(&val[0], &val[0], 8);      // val <<= 8
        mpz_add_ui(&val[0], &val[0], byte);     // val |= byte; that is, val += byte
    }

    if (negative) {
        // this is micro-omg-optimize-efficient because gmp uses sign and magnitude
        // https://gmplib.org/manual/Integer-Internals.html#Integer-Internals
        // mpz_neg doesn't compile because a zig bug
        //mpz_neg(&val[0], &val[0]);
        mpz_mul_si(&val[0], &val[0], -1);
    }
    return Object.init(interp, typ, objtyp.ObjectData{ .IntegerData = Data{ .interp = interp, .mpz = val }});
}

test "creating integers" {
    var interp: Interp = undefined;
    interp.init();
    defer interp.deinit();

    const a = try newFromFunnyAsdaBytecodeNumberString(&interp, "ab", false);
    defer a.decref();
    const b = try newFromFunnyAsdaBytecodeNumberString(&interp, "ab", true);
    defer b.decref();

    var a_value: mpz_t = undefined;
    var b_value: mpz_t = undefined;
    mpz_init_set_si(&a_value[0], ('a'<<8)|'b');
    mpz_init_set_si(&b_value[0], -( ('a'<<8)|'b' ));
    defer mpz_clear(&a_value[0]);
    defer mpz_clear(&b_value[0]);

    std.debug.assert(mpz_cmp(&a.data.IntegerData.mpz[0], &a_value[0]) == 0);
    std.debug.assert(mpz_cmp(&b.data.IntegerData.mpz[0], &b_value[0]) == 0);
}
