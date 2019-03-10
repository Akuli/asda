const std = @import("std");

pub const boolean = @import("boolean.zig");
pub const function = @import("function.zig");
pub const integer = @import("integer.zig");
pub const scope = @import("scope.zig");
pub const string = @import("string.zig");

pub fn debugTypes() void {
    std.debug.warn("boolean             = {*}\n", boolean.typ);
    std.debug.warn("void function       = {*}\n", function.void_type);
    std.debug.warn("returning function  = {*}\n", function.returning_type);
    std.debug.warn("scope               = {*}\n", scope.typ);
    std.debug.warn("string              = {*}\n", string.typ);
    std.debug.warn("integer             = {*}\n", integer.typ);
}

//test "debugTypes" { debugTypes(); }
