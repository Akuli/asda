const std = @import("std");
const assert = std.debug.assert;
const Type = @import("../object.zig").Type;
const Object = @import("../object.zig").Object;
const ObjectData = @import("../object.zig").ObjectData;


pub const Data = struct {
    allocator: *std.mem.Allocator,
    unicode: []u32,

    pub fn init(allocator: *std.mem.Allocator, unicode: []u32) ObjectData {
        const value = Data{ .allocator = allocator, .unicode = unicode };
        return ObjectData{ .value = ObjectData.Value{ .StringValue = value }};
    }

    pub fn destroy(self: Data) void {
        self.allocator.free(self.unicode);
    }
};

var type_value = Type.init([]*Object { });
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

    // the realloc is making the buf smaller, so it "can't" fail
    buf = allocator.realloc(u32, buf, i) catch unreachable;
    return newNoCopy(allocator, buf);
}

test "string newFromUtf8" {
    const string = try newFromUtf8(std.heap.c_allocator, "Pöö");
    defer string.decref();

    const arr = []u32{ 'P', 0xf6, 0xf6 };
    assert(std.mem.eql(u32, string.data.value.StringValue.unicode, arr));
}

test "empty string" {
    const string = try newFromUtf8(std.heap.c_allocator, "");
    defer string.decref();
    assert(string.data.value.StringValue.unicode.len == 0);
}
