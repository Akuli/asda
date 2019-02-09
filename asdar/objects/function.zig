const std = @import("std");
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;


pub const FunctionType = struct {
    argtypes: []const *objtyp.Type,
    returntype: ?*objtyp.Type,

    pub fn initComptimeVoid(argtypes: []const *objtyp.Type) objtyp.Type {
        return objtyp.Type{ .Function = FunctionType{ .argtypes = argtypes, .returntype = null } };
    }
    pub fn initComptimeReturning(argtypes: []const *objtyp.Type, returntype: *objtyp.Type) objtyp.Type {
        return objtyp.Type{ .Function = FunctionType{ .argtypes = argtypes, .returntype = returntype } };
    }
};

pub const Fn = union(enum) {
    Returning: fn([]const *Object) anyerror!*Object,
    Void: fn([]const *Object) anyerror!void,
};

pub const Data = struct {
    name: []const u8,    // should be e.g. statically allocated, this won't handle freeing
    zig_fn: Fn,
};

fn testFn(objs: []const *Object) anyerror!*Object {
    return objs[0];
}

test "function data creating" {
    const assert = std.debug.assert;
    const object_type = @import("../object.zig").object_type;

    const argtypes = []*objtyp.Type{ object_type, object_type };
    const type2 = FunctionType{ .argtypes = argtypes[0..], .returntype = object_type };
    const func_data = Data{ .name = "testfunc", .zig_fn = Fn{ .Returning = testFn }};
    assert(std.mem.eql(u8, func_data.name, "testfunc"));
    assert(func_data.zig_fn.Returning == testFn);
}

pub fn newComptime(name: []const u8, typ: *objtyp.Type, zig_fn: Fn) Object {
    // TODO: figure out why this doesn't work
    //switch(zig_fn) {
    //    Fn.Returning => std.debug.assert(typ.Function.returntype != null),
    //    Fn.Void => std.debug.assert(typ.Function.returntype == null),
    //}

    const data = objtyp.ObjectData{ .FunctionValue = Data{ .name = name, .zig_fn = zig_fn }};
    return Object.initComptime(typ, data);
}

test "function newComptime" {
    const assert = std.debug.assert;
    const string = @import("string.zig");

    comptime {
        var functype = FunctionType.initComptimeReturning([]const *objtyp.Type{ string.typ }, string.typ);
        var func_obj_value = newComptime("blah", &functype, Fn{ .Returning = testFn });
        const func_obj = &func_obj_value;

        assert(func_obj.refcount == 1);
    }
}

pub fn callReturning(func: *Object, args: []const *Object) !*Object {
    return func.data.value.FunctionValue.zig_fn.Returning(args);
}

pub fn callVoid(func: *Object, args: []const *Object) !void {
    try func.data.FunctionValue.zig_fn.Void(args);
}
