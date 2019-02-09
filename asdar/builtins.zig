const std = @import("std");
const objects = @import("objects/index.zig");
const Object = @import("object.zig").Object;
const Type = @import("object.zig").Type;

fn printFn(args: []const *Object) anyerror!void {
    // TODO: don't hardcode std.heap.c_allocator
    // TODO: is calling getStdOut every time bad?
    std.debug.assert(args.len == 1);
    const utf8 = try objects.string.toUtf8(std.heap.c_allocator, args[0]);
    defer std.heap.c_allocator.free(utf8);

    const stdout = try std.io.getStdOut();
    try stdout.write(utf8);
    try stdout.write("\n");
}

test "builtins printFn" {
    const s = try objects.string.newFromUtf8(std.heap.c_allocator, "Hello World!");
    try printFn([]const*Object{ s });
}

var print_type = objects.function.FunctionType.initComptimeVoid([]const *Type{ objects.string.typ });
var print_value = objects.function.newComptime("blah", &print_type, objects.function.Fn{ .Void = printFn });
pub const print = &print_value;

pub const builtin_array = []const *Object {
    print,
    objects.boolean.TRUE,
    objects.boolean.FALSE,
    // TODO: add next[T]() here
};
