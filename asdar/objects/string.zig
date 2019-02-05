const std = @import("std");
const Object = @import("../object.zig").Object;
const ObjectData = @import("../object.zig").ObjectData;
const Type = @import("../object.zig").Type;
const AllocError = std.mem.Allocator.Error;


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
pub fn newNoCopy(allocator: *std.mem.Allocator, unicode: []u32) AllocError!*Object {
    return Object.init(allocator, typ, Data.init(allocator, unicode));
}

test "string newNoCopy" {
    const assert = std.debug.assert;

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
pub fn new(allocator: *std.mem.Allocator, unicode: []const u32) AllocError!*Object {
    const dup = try std.mem.dupe(allocator, u32, unicode);
    errdefer allocator.free(dup);
    return newNoCopy(allocator, dup);
}

test "string new" {
    const assert = std.debug.assert;

    // TODO: figure out how to create the array without mallocing
    const buf = try std.heap.c_allocator.alloc(u32, 5);
    defer std.heap.c_allocator.free(buf);
    buf[0] = 'a';
    buf[1] = 'b';
    buf[2] = 'c';
    buf[3] = 'd';
    buf[4] = 'e';

    const string = try new(std.heap.c_allocator, buf);
    defer string.decref();

    assert(string.data.value.StringValue.unicode[2] == 'c');
}
