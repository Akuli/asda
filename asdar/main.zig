const std = @import("std");
const Object = @import("object.zig").Object;
const objects = @import("objects/index.zig");

// because std.os.exit() doesn't run defers, which would otherwise leak memory
fn mainInner(args: []const []u8) anyerror!u8 {
    if (args.len != 2) {
        // std.debug.warn writes to stderr
        std.debug.warn("Usage: {} bytecodefile\n", args[0]);
        return 2;
    }

    return 0;
}

// can't get this to compile :(
//test "mainInner" {
//    const assert = std.debug.assert;
//    const arg1: []const u8 = "ab";
//    const args: [][]const u8 = [][]const u8{ arg1, arg2 };
//    assert(mainInner(args) == 2);
//}

pub fn main() !void {
    var status: u8 = undefined;
    {
        var args = try std.os.argsAlloc(std.heap.c_allocator);
        defer std.os.argsFree(std.heap.c_allocator, args);
        status = try mainInner(args);
    }

    if (status != 0) {
        std.os.exit(status);
    }
}
