const std = @import("std");
const Interp = @import("../interp.zig").Interp;
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
    Returning: fn(interp: *Interp, data: *objtyp.ObjectData, []const *Object) anyerror!*Object,
    Void: fn(interp: *Interp, data: *objtyp.ObjectData, []const *Object) anyerror!void,
};

pub const Data = struct {
    allocator: ?*std.mem.Allocator,    // for allocator.destroy()ing passed_data,   TODO: replace with an interp pointer
    name: []const u8,   // should be e.g. statically allocated, this won't handle freeing
    zig_fn: Fn,
    passed_data: *objtyp.ObjectData,   // must be pointer to avoid union that contains itself, which is why allocator is needed

    fn initComptime(name: []const u8, zig_fn: Fn, passed_data: *objtyp.ObjectData) Data {
        return Data{ .allocator = null, .name = name, .zig_fn = zig_fn, .passed_data = passed_data };
    }

    fn init(allocator: *std.mem.Allocator, name: []const u8, zig_fn: Fn, passed_data: *objtyp.ObjectData) Data {
        return Data{ .allocator = allocator, .name = name, .zig_fn = zig_fn, .passed_data = passed_data };
    }

    pub fn destroy(self: Data) void {
        if (self.allocator) |allocator| {
            self.passed_data.*.destroy();
            allocator.destroy(self.passed_data);
        }
    }
};

fn testFn(interp: *Interp, data: *objtyp.ObjectData, objs: []const *Object) anyerror!*Object {
    return objs[0];
}

var no_data = objtyp.ObjectData{ .NoData = void{} };

// passed_data should be e.g. statically allocated, and will NOT be destroyed
// if it isn't, make it statically allocated or use init()
pub fn newComptime(name: []const u8, typ: *objtyp.Type, zig_fn: Fn, passed_data: ?*objtyp.ObjectData) Object {
    // TODO: figure out why this doesn't work
    //switch(zig_fn) {
    //    Fn.Returning => std.debug.assert(typ.Function.returntype != null),
    //    Fn.Void => std.debug.assert(typ.Function.returntype == null),
    //}

    const data = objtyp.ObjectData{ .FunctionData = Data.initComptime(name, zig_fn, passed_data orelse &no_data) };
    return Object.initComptime(typ, data);
}

// passed_data should be allocated with interp.object_allocator
pub fn new(interp: *Interp, name: []const u8, typ: *objtyp.Type, zig_fn: Fn, passed_data: ?*objtyp.ObjectData) !*Object {
    const passed_data_notnull = passed_data orelse blk: {
        const res = try interp.object_allocator.create(objtyp.ObjectData);
        res.* = no_data;
        break :blk res;
        // FIXME: should errdefer a dealloc nicely
    };
    const data = objtyp.ObjectData{ .FunctionData = Data.init(interp.object_allocator, name, zig_fn, passed_data_notnull) };
    return Object.init(interp, typ, data);
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

pub fn callReturning(interp: *Interp, func: *Object, args: []const *Object) !*Object {
    return try func.data.FunctionData.zig_fn.Returning(interp, func.data.FunctionData.passed_data, args);
}

pub fn callVoid(interp: *Interp, func: *Object, args: []const *Object) !void {
    try func.data.FunctionData.zig_fn.Void(interp, func.data.FunctionData.passed_data, args);
}
