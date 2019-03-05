const std = @import("std");
const bcreader = @import("bcreader.zig");
const Interp = @import("interp.zig").Interp;
const misc = @import("misc.zig");
const runner = @import("runner.zig");


// because std.os.exit() doesn't run defers, which would otherwise leak memory
fn mainInner(args: []const []u8) u8 {
    if (args.len != 2) {
        // std.debug.warn writes to stderr
        std.debug.warn("Usage: {} bytecodefile\n", args[0]);
        return 2;
    }

    const program = args[0];
    const filename = args[1];

    if (std.os.File.openRead(filename)) |f| {
        defer f.close();

        var interp: Interp = undefined;
        interp.init();
        defer interp.deinit();

        const stream = &f.inStream().stream;    // no idea why the last .stream is needed, but this works :D
        var errorByte: ?u8 = null;    // TODO: don't use a special value
        if (bcreader.readByteCode(&interp, stream, &errorByte)) |code| {
            defer code.destroy();

            if (runner.runFile(&interp, code)) |_| {
                // ok
            } else |err| {
                std.debug.warn("{}: running {} failed: {}\n", program, filename, misc.errorToString(err));
            }
        } else |err| {
            std.debug.warn("{}: cannot read {}: {}", program, filename, misc.errorToString(err));
            if (errorByte) |byte| {
                std.debug.warn(" 0x{x}", byte);
            }
            std.debug.warn("\n");
            return 1;
        }
    } else |err| {
        std.debug.warn("{}: cannot open {}: {}\n", program, filename, misc.errorToString(err));
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
