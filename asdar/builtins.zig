const std = @import("std");
const Interp = @import("interp.zig").Interp;
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const objects = @import("objects/index.zig");

fn printFn(interp: *Interp, data: *objtyp.ObjectData, args: []const *Object) anyerror!void {
    std.debug.assert(args.len == 1);
    const utf8 = try objects.string.toUtf8(interp.object_allocator, args[0]);
    defer interp.object_allocator.free(utf8);

    // TODO: is calling getStdOut every time bad?
    const stdout = try std.io.getStdOut();
    try stdout.write(utf8);
    try stdout.write("\n");
}

test "builtins printFn" {
    var interp: Interp = undefined;
    try interp.init();
    defer interp.deinit();

    var no_data = objtyp.ObjectData{ .NoData = void{} };
    const s = try objects.string.newFromUtf8(&interp, "Hello World!");
    defer s.decref();
    try printFn(&interp, &no_data, []const *Object{ s });
}

var print_value = objects.function.newComptime(objects.function.Fn{ .Void = printFn }, null);
pub const print = &print_value;

pub const object_array = []const *Object {
    print,
    objects.boolean.TRUE,
    objects.boolean.FALSE,
    // TODO: add next[T]() here
};
pub const type_array = []const *objtyp.Type{
    objects.string.typ,
    objects.integer.typ,
    objects.boolean.typ,
    objects.boolean.typ,     // FIXME: should be Object, but types don't have parent types and inheritance yet
};
