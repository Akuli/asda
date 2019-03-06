const std = @import("std");
const assert = std.debug.assert;
const Interp = @import("../interp.zig").Interp;
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;


pub const Data = struct {
    allocator: *std.mem.Allocator,
    unicode: []u32,

    pub fn init(allocator: *std.mem.Allocator, unicode: []u32) objtyp.ObjectData {
        const value = Data{ .allocator = allocator, .unicode = unicode };
        return objtyp.ObjectData{ .StringData = value };
    }

    pub fn destroy(self: Data, decref_refs: bool, free_nonrefs: bool) void {
        if (free_nonrefs) {
            self.allocator.free(self.unicode);
        }
    }
};

var type_value = objtyp.Type{ .Basic = objtyp.BasicType.init([]*Object { }) };
pub const typ = &type_value;

// unlike with new(), the string is responsible for freeing the unicode
// unicode must have been allocated with interp.object_allocator
// example usage:
//
//    var string: *Object = undefined;
//    {
//        const buf = try interp.object_allocator.alloc(u32, 5);
//        errdefer allocator.free(buf);
//        buf[0] = 'a';
//        buf[1] = 'b';
//        buf[2] = 'c';
//        buf[3] = 'd';
//        buf[4] = 'e';
//
//        string = try objects.string.newNoCopy(interp, buf);
//    }
//    defer string.decref();
//
//    // use the string
pub fn newNoCopy(interp: *Interp, unicode: []u32) !*Object {
    return Object.init(interp, typ, Data.init(interp.object_allocator, unicode));
}

test "string newNoCopy" {
    var interp: Interp = undefined;
    interp.init();
    defer interp.deinit();

    var string: *Object = undefined;
    {
        const buf = try interp.object_allocator.alloc(u32, 5);
        errdefer interp.object_allocator.free(buf);
        buf[0] = 'a';
        buf[1] = 'b';
        buf[2] = 'c';
        buf[3] = 'd';
        buf[4] = 'e';
        string = try newNoCopy(&interp, buf);
    }
    defer string.decref();
}

// creates a new string that uses a copy of the unicode
pub fn new(interp: *Interp, unicode: []const u32) !*Object {
    const dup = try std.mem.dupe(interp.object_allocator, u32, unicode);
    errdefer interp.object_allocator.free(dup);
    return newNoCopy(interp, dup);
}

test "string new" {
    var interp: Interp = undefined;
    interp.init();
    defer interp.deinit();

    const arr = []u32{ 'a', 'b', 'c' };

    const string = try new(&interp, arr);
    defer string.decref();
}

// the nicest way to create a string object
// the utf8 can be freed after calling this
pub fn newFromUtf8(interp: *Interp, utf8: []const u8) !*Object {
    // utf8 is never less bytes than the unicode, so utf8.len works here
    var buf: []u32 = try interp.object_allocator.alloc(u32, utf8.len);
    errdefer interp.object_allocator.free(buf);

    var i: usize = 0;
    var it = (try std.unicode.Utf8View.init(utf8)).iterator();
    while (it.nextCodepoint()) |codepoint| {
        buf[i] = codepoint;
        i += 1;
    }

    buf = interp.object_allocator.shrink(u32, buf, i);
    return newNoCopy(interp, buf);
}

// returns the value of a string as unicode
// return value must not be freed
pub fn toUnicode(str: *Object) []const u32 {
    return str.data.StringData.unicode;
}

// returns the utf8 of a string, return value must be freed after calling
pub fn toUtf8(allocator: *std.mem.Allocator, str: *Object) ![]u8 {
    const codepoints = toUnicode(str);

    var result = std.ArrayList(u8).init(allocator);
    errdefer result.deinit();
    try result.ensureCapacity(codepoints.len);   // superstitious optimization for ascii strings

    for (codepoints) |p| {
        var buf = []u8{ 0, 0, 0, 0 };
        const n = try std.unicode.utf8Encode(p, buf[0..]);
        try result.appendSlice(buf[0..n]);
    }

    return result.toOwnedSlice();
}

test "string newFromUtf8 toUnicode toUtf8" {
    var interp: Interp = undefined;
    interp.init();
    defer interp.deinit();

    const string = try newFromUtf8(&interp, "Pöö");
    defer string.decref();

    const arr = []u32{ 'P', 0xf6, 0xf6 };
    assert(std.mem.eql(u32, toUnicode(string), arr));

    const utf8 = try toUtf8(std.heap.c_allocator, string);
    defer std.heap.c_allocator.free(utf8);
    assert(std.mem.eql(u8, utf8, "Pöö"));
}

test "string empty" {
    var interp: Interp = undefined;
    interp.init();
    defer interp.deinit();

    const string = try newFromUtf8(&interp, "");
    defer string.decref();

    assert(toUnicode(string).len == 0);

    const utf8 = try toUtf8(std.heap.c_allocator, string);
    defer std.heap.c_allocator.free(utf8);
    assert(utf8.len == 0);
}
