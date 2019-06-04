const std = @import("std");
const Interp = @import("../interp.zig").Interp;
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;
const objects = @import("index.zig");

use @cImport(@cInclude("gmp.h"));


fn toStringFn(interp: *Interp, data: *objtyp.ObjectData, args: []const *Object) anyerror!*Object {
    std.debug.assert(args.len == 1);
    const mpz = args[0].data.IntegerData.mpz;

    const base = 10;
    const buf = try interp.object_allocator.alloc(u8, mpz_sizeinbase(&mpz[0], base) + 2);   // see mpz_get_str docs
    defer interp.object_allocator.free(buf);

    _ = mpz_get_str(buf.ptr, base, &mpz[0]);

    const len = std.mem.len(u8, buf.ptr);
    return try objects.string.newFromUtf8(interp, buf[0..len]);
}
var tostring_value = objects.function.newComptime(objects.function.Fn{ .Returning = toStringFn }, null);


pub fn debugPrint(obj: *Object) void {
    const mpz = obj.data.IntegerData.mpz;
    const buf = std.heap.c_allocator.alloc(u8, mpz_sizeinbase(&mpz[0], 10) + 2) catch unreachable;
    defer std.heap.c_allocator.free(buf);
    _ = mpz_get_str(buf.ptr, 10, &mpz[0]);
    const len = std.mem.len(u8, buf.ptr);
    std.debug.warn("{}\n", buf[0..len]);
}


var type_value = objtyp.Type.init([]objtyp.Attribute {
    objtyp.Attribute{ .is_method = true, .value = &tostring_value },
});
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

// don't do anything with the mpz after passing it to this
fn newFromMpz(interp: *Interp, mpz: mpz_t) !*Object {
    var val = try interp.object_allocator.create(mpz_t);
    errdefer interp.object_allocator.destroy(val);
    val.* = mpz;
    return try Object.init(interp, typ, objtyp.ObjectData{ .IntegerData = Data{ .interp = interp, .mpz = val }});
}

// integers are mutable, and therefore this is useful only for testing purposes
fn copy(obj: *Object) !*Object {
    var mpz: mpz_t = undefined;
    mpz_init_set(&mpz[0], &obj.data.IntegerData.mpz.*[0]);
    errdefer mpz_clear(&mpz[0]);
    return try newFromMpz(obj.data.IntegerData.interp, mpz);
}

pub fn newFromFunnyAsdaBytecodeNumberString(interp: *Interp, s: []const u8) !*Object {
    var val: mpz_t = undefined;
    mpz_init2(&val[0], s.len*8);    // val = 0
    errdefer mpz_clear(&val[0]);

    for (s) |byte| {
        mpz_mul_2exp(&val[0], &val[0], 8);      // val <<= 8
        mpz_add_ui(&val[0], &val[0], byte);     // val |= byte; that is, val += byte
    }
    return newFromMpz(interp, val);
}

test "creating integers" {
    var interp: Interp = undefined;
    try interp.init();
    defer interp.deinit();

    const a = try newFromFunnyAsdaBytecodeNumberString(&interp, "ab");
    defer a.decref();

    var a_value: mpz_t = undefined;
    mpz_init_set_si(&a_value[0], ('a'<<8)|'b');
    defer mpz_clear(&a_value[0]);

    std.testing.expect(mpz_cmp(&a.data.IntegerData.mpz[0], &a_value[0]) == 0);
}


pub fn compare(a: *Object, b: *Object) std.mem.Compare {
    const val = mpz_cmp(&a.data.IntegerData.mpz[0], &b.data.IntegerData.mpz[0]);
    if (val > 0) {
        return std.mem.Compare.GreaterThan;
    }
    if (val < 0) {
        return std.mem.Compare.LessThan;
    }
    return std.mem.Compare.Equal;
}


// magic is better than repetition
const mpz_t_inner = @typeInfo(mpz_t).Array.child;

const MpzWrapper = struct {
    const FType = union(enum) {
        Binary: extern fn([*]mpz_t_inner, [*]const mpz_t_inner, [*]const mpz_t_inner) void,
        SiMinus1: extern fn([*]mpz_t_inner, [*]const mpz_t_inner, c_long) void,
    };
    f: comptime FType,

    // these are anyerror to make doing more magic easier
    fn inPlaceBinary(self: MpzWrapper, a: **Object, b: *Object) anyerror!void {
        std.debug.assert(a.*.data.IntegerData.interp == b.data.IntegerData.interp);
        const interp = a.*.data.IntegerData.interp;
        const a_mpz = a.*.data.IntegerData.mpz;
        const b_mpz = b.*.data.IntegerData.mpz;

        // integers are mutable in gnu gmp, but immutable in asda
        if (a.*.refcount == 1) {
            // can modify it in place, nobody will notice
            self.f.Binary(a_mpz, a_mpz, b_mpz);
        } else {
            var res: mpz_t = undefined;
            mpz_init(&res[0]);
            errdefer mpz_clear(&res[0]);

            self.f.Binary(&res, a_mpz, b_mpz);
            a.*.decref();
            a.* = try newFromMpz(interp, res);
        }
    }

    fn inPlaceSiMinus1(self: MpzWrapper, a: **Object) anyerror!void {
        const interp = a.*.data.IntegerData.interp;
        const mpz = a.*.data.IntegerData.mpz;

        if (a.*.refcount == 1) {
            self.f.SiMinus1(mpz, mpz, -1);
        } else {
            var res: mpz_t = undefined;
            mpz_init(&res[0]);
            errdefer mpz_clear(&res[0]);

            self.f.SiMinus1(&res, mpz, -1);
            a.*.decref();
            a.* = try newFromMpz(interp, res);
        }
    }
};

// takes one argument, a, and does: a = -a
// mpz_neg doesn't compile because a zig bug, but mpz_mul_si works
pub const negateInPlace = (MpzWrapper{ .f = MpzWrapper.FType{.SiMinus1=mpz_mul_si} }).inPlaceSiMinus1;

// takes two arguments, a and b, and does: a = a + b
pub const addInPlace = (MpzWrapper{ .f = MpzWrapper.FType{.Binary=mpz_add} }).inPlaceBinary;

// takes two arguments, a and b, and does: a = a - b
pub const subInPlace = (MpzWrapper{ .f = MpzWrapper.FType{.Binary=mpz_sub} }).inPlaceBinary;

// takes two arguments, a and b, and does: a = a * b
pub const mulInPlace = (MpzWrapper{ .f = MpzWrapper.FType{.Binary=mpz_mul} }).inPlaceBinary;


test "negating and compare" {
    var interp: Interp = undefined;
    try interp.init();
    defer interp.deinit();
    const assert = std.testing.expect;

    var a = try newFromFunnyAsdaBytecodeNumberString(&interp, []u8{ 123 });
    defer a.decref();
    const b = try copy(a);
    defer b.decref();

    assert(compare(a, b) == std.mem.Compare.Equal);
    try negateInPlace(&a);
    assert(compare(a, b) == std.mem.Compare.LessThan);
    try negateInPlace(&a);
    assert(compare(a, b) == std.mem.Compare.Equal);

    const c = a;
    c.incref();
    defer c.decref();

    assert(compare(a, b) == std.mem.Compare.Equal);
    try negateInPlace(&a);
    assert(compare(a, b) == std.mem.Compare.LessThan);
    try negateInPlace(&a);
    assert(compare(a, b) == std.mem.Compare.Equal);
}

test "adding" {
    var interp: Interp = undefined;
    try interp.init();
    defer interp.deinit();
    const assert = std.testing.expect;

    const twelve = try newFromFunnyAsdaBytecodeNumberString(&interp, []u8{ 12 });
    defer twelve.decref();
    const twentyfour = try newFromFunnyAsdaBytecodeNumberString(&interp, []u8{ 24 });
    defer twentyfour.decref();
    const thirtysix = try newFromFunnyAsdaBytecodeNumberString(&interp, []u8{ 36 });
    defer thirtysix.decref();

    var a = try copy(twelve);
    defer a.decref();

    try addInPlace(&a, twelve);
    assert(compare(a, twentyfour) == std.mem.Compare.Equal);

    const b = a;
    b.incref();
    defer b.decref();

    try addInPlace(&a, twelve);
    assert(compare(a, thirtysix) == std.mem.Compare.Equal);
}
