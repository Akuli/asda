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
    allocator: ?*std.mem.Allocator,    // for allocator.destroy()ing passed_data
    name: []const u8,   // should be e.g. statically allocated, this won't handle freeing
    zig_fn: Fn,
    passed_data: *objtyp.ObjectData,   // must be pointer to avoid union that contains itself, which is why allocator is needed

    fn initComptime(name: []const u8, zig_fn: Fn, passed_data: *objtyp.ObjectData) Data {
        return Data{ .allocator = null, .name = name, .zig_fn = zig_fn, .passed_data = passed_data };
    }

    fn init(allocator: *std.mem.Allocator, name: []const u8, zig_fn: Fn, passed_data: objtyp.ObjectData) !Data {
        const pdata = try allocator.create(objtyp.ObjectData);
        errdefer allocator.destroy(pdata);
        pdata.* = passed_data;
        return Data{ .allocator = allocator, .name = name, .zig_fn = zig_fn, .passed_data = pdata };
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

// passed_data should be e.g. statically allocated, and will NOT be destroyed
// if it isn't, make it statically allocated or use init()
pub fn newComptimeWithPassedData(name: []const u8, typ: *objtyp.Type, zig_fn: Fn, passed_data: *objtyp.ObjectData) Object {
    // TODO: figure out why this doesn't work
    //switch(zig_fn) {
    //    Fn.Returning => std.debug.assert(typ.Function.returntype != null),
    //    Fn.Void => std.debug.assert(typ.Function.returntype == null),
    //}

    const data = objtyp.ObjectData{ .FunctionData = Data.initComptime(name, zig_fn, passed_data) };
    return Object.initComptime(typ, data);
}

var no_data = objtyp.ObjectData{ .NoData = void{} };

pub fn newComptime(name: []const u8, typ: *objtyp.Type, zig_fn: Fn) Object {
    return newComptimeWithPassedData(name, typ, zig_fn, &no_data);
}

// tests newComptimeWithPassedData because newComptime calls it
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
    return try func.data.value.FunctionValue.zig_fn.Returning(interp, func.data.FunctionData.passed_data, args);
}

pub fn callVoid(interp: *Interp, func: *Object, args: []const *Object) !void {
    try func.data.FunctionData.zig_fn.Void(interp, func.data.FunctionData.passed_data, args);
}
