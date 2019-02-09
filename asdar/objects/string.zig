const std = @import("std");
const assert = std.debug.assert;
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;


pub const Data = struct {
    allocator: *std.mem.Allocator,
    unicode: []u32,

    pub fn init(allocator: *std.mem.Allocator, unicode: []u32) objtyp.ObjectData {
        const value = Data{ .allocator = allocator, .unicode = unicode };
        return objtyp.ObjectData{ .StringValue = value };
    }

    pub fn destroy(self: Data) void {
        self.allocator.free(self.unicode);
    }
};

var type_value = objtyp.Type{ .Basic = objtyp.BasicType.init([]*Object { }) };
pub const typ = &type_value;

// unlike with new(), the string is responsible for freeing the unicode
// example usage:
//
//    var string: *Object = undefined;
//    {
//        const buf = try allocator.alloc(u32, 5);
//        errdefer allocator.free(buf);
//        buf[0] = 'a';
//        buf[1] = 'b';
//        buf[2] = 'c';
//        buf[3] = 'd';
//        buf[4] = 'e';
//
//        string = try objects.string.newNoCopy(std.heap.c_allocator, buf);
//    }
//    defer string.decref();
//
//    // use the string
pub fn newNoCopy(allocator: *std.mem.Allocator, unicode: []u32) !*Object {
    return Object.init(allocator, typ, Data.init(allocator, unicode));
}

test "string newNoCopy" {
    var string: *Object = undefined;
    {
        const buf = try std.heap.c_allocator.alloc(u32, 5);
        errdefer std.heap.c_allocator.free(buf);
        buf[0] = 'a';
        buf[1] = 'b';
        buf[2] = 'c';
        buf[3] = 'd';
        buf[4] = 'e';
        string = try newNoCopy(std.heap.c_allocator, buf);
    }
    defer string.decref();

    assert(string.data.value.StringValue.unicode[2] == 'c');
}

// creates a new string that uses a copy of the unicode
pub fn new(allocator: *std.mem.Allocator, unicode: []const u32) !*Object {
    const dup = try std.mem.dupe(allocator, u32, unicode);
    errdefer allocator.free(dup);
    return newNoCopy(allocator, dup);
}

test "string new" {
    const arr = []u32{ 'a', 'b', 'c' };

    const string = try new(std.heap.c_allocator, arr);
    defer string.decref();

    assert(std.mem.eql(u32, arr, string.data.value.StringValue.unicode));
}

// the nicest way to create a string object
// the utf8 can be freed after calling this
pub fn newFromUtf8(allocator: *std.mem.Allocator, utf8: []const u8) !*Object {
    // utf8 is never less bytes than the unicode, so utf8.len works here
    var buf: []u32 = try allocator.alloc(u32, utf8.len);
    errdefer allocator.free(buf);

    var i: usize = 0;
    var it = (try std.unicode.Utf8View.init(utf8)).iterator();
    while (it.nextCodepoint()) |codepoint| {
        buf[i] = codepoint;
        i += 1;
    }

    buf = allocator.shrink(u32, buf, i);
    return newNoCopy(allocator, buf);
}

// returns the value of a string as unicode
// return value must not be freed
pub fn toUnicode(str: *Object) []const u32 {
    return str.data.StringValue.unicode;
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
    const string = try newFromUtf8(std.heap.c_allocator, "Pöö");
    defer string.decref();

    const arr = []u32{ 'P', 0xf6, 0xf6 };
    assert(std.mem.eql(u32, toUnicode(string), arr));

    const utf8 = try toUtf8(std.heap.c_allocator, string);
    defer std.heap.c_allocator.free(utf8);
    assert(std.mem.eql(u8, utf8, "Pöö"));
}

test "string empty" {
    const string = try newFromUtf8(std.heap.c_allocator, "");
    defer string.decref();

    assert(toUnicode(string).len == 0);

    const utf8 = try toUtf8(std.heap.c_allocator, string);
    defer std.heap.c_allocator.free(utf8);
    assert(utf8.len == 0);
}
