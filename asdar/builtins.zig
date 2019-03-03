const std = @import("std");
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const objects = @import("objects/index.zig");

fn printFn(data: *objtyp.ObjectData, args: []const *Object) anyerror!void {
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
    var no_data = objtyp.ObjectData{ .NoData = void{} };
    const s = try objects.string.newFromUtf8(std.heap.c_allocator, "Hello World!");
    try printFn(&no_data, []const *Object{ s });
}

var print_type = objects.function.FunctionType.initComptimeVoid([]const *objtyp.Type{ objects.string.typ });
var print_value = objects.function.newComptime("print", &print_type, objects.function.Fn{ .Void = printFn });
pub const print = &print_value;

pub const object_array = []const *Object {
    print,
    objects.boolean.TRUE,
    objects.boolean.FALSE,
    // TODO: add next[T]() here
};
pub const type_array = []const *objtyp.Type{
    objects.string.typ,
    objects.boolean.typ,     // FIXME: should be int, but there is no int yet :(
    objects.boolean.typ,
    objects.boolean.typ,     // FIXME: should be Object, but types don't have parent types and inheritance yet
};
