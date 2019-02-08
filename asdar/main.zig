const std = @import("std");
const Object = @import("object.zig").Object;
const bcreader = @import("bcreader.zig");
const misc = @import("misc.zig");
const runner = @import("runner.zig");

// because std.os.exit() doesn't run defers, which would otherwise leak memory
fn mainInner(args: []const []u8) u8 {
    const allocator = std.heap.c_allocator;

    if (args.len != 2) {
        // std.debug.warn writes to stderr
        std.debug.warn("Usage: {} bytecodefile\n", args[0]);
        return 2;
    }

    if (std.os.File.openRead(args[1])) |f| {
        defer f.close();

        const stream = &f.inStream().stream;
        if (bcreader.readByteCode(allocator, stream)) |res| {
            switch(res) {
                bcreader.ReadResult.InvalidOpByte => |byte| {
                    std.debug.warn("{}: cannot read {}: Invalid op byte 0x{x}\n", args[0], args[1], byte);
                    return 1;
                },
                bcreader.ReadResult.ByteCode => |code| {
                    defer code.destroy();

                    code.debugDump();
                    if (runner.runFile(allocator, code)) |_| {
                        // ok
                    } else |err| {
                        std.debug.warn("{}: running {} failed: {}\n", args[0], args[1], misc.errorToString(err));
                    }
                    code.debugDump();
                },
            }
        } else |err| {
            std.debug.warn("{}: cannot read {}: {}\n", args[0], args[1], misc.errorToString(err));
            return 1;
        }
    } else |err| {
        std.debug.warn("{}: cannot open {}: {}\n", args[0], args[1], misc.errorToString(err));
        return 1;
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
        status = mainInner(args);
    }

    if (status != 0) {
        std.os.exit(status);
    }
}
