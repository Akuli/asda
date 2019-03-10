const std = @import("std");
const Interp = @import("../interp.zig").Interp;
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;


var void_type_value = objtyp.Type.init([]objtyp.Attribute { });
var returning_type_value = objtyp.Type.init([]objtyp.Attribute { });
pub const void_type = &void_type_value;
pub const returning_type = &returning_type_value;

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

    pub fn destroy(self: Data, decref_refs: bool, free_nonrefs: bool) void {
        if (self.allocator) |allocator| {
            self.passed_data.*.destroy(decref_refs, free_nonrefs);
            if (free_nonrefs) {
                allocator.destroy(self.passed_data);
            }
        }
    }
};

fn testFn(interp: *Interp, data: *objtyp.ObjectData, objs: []const *Object) anyerror!*Object {
    return objs[0];
}

var no_data = objtyp.ObjectData{ .NoData = void{} };

// passed_data should be e.g. statically allocated, and will NOT be destroyed
// if it isn't, make it statically allocated or use init()
pub fn newComptime(name: []const u8, zig_fn: Fn, passed_data: ?*objtyp.ObjectData) Object {
    const data = objtyp.ObjectData{ .FunctionData = Data.initComptime(name, zig_fn, passed_data orelse &no_data) };
    const typ = switch(zig_fn) {
        Fn.Returning => returning_type,
        Fn.Void => returning_type,
    };
    return Object.initComptime(typ, data);
}

// passed_data should be allocated with interp.object_allocator
pub fn new(interp: *Interp, name: []const u8, zig_fn: Fn, passed_data: ?objtyp.ObjectData) !*Object {
    const data_ptr = try interp.object_allocator.create(objtyp.ObjectData);
    errdefer interp.object_allocator.destroy(data_ptr);
    data_ptr.* = passed_data orelse no_data;

    const typ = switch(zig_fn) {
        Fn.Returning => returning_type,
        Fn.Void => returning_type,
    };
    const data = objtyp.ObjectData{ .FunctionData = Data.init(interp.object_allocator, name, zig_fn, data_ptr) };
    return try Object.init(interp, typ, data);
}

test "function newComptime" {
    const assert = std.debug.assert;
    const string = @import("string.zig");

    comptime {
        var func_obj_value = newComptime("blah", Fn{ .Returning = testFn }, null);
        const func_obj = &func_obj_value;

        assert(func_obj.refcount == 1);
    }
}

pub fn callReturning(interp: *Interp, func: *Object, args: []const *Object) !*Object {
    return try func.data.FunctionData.zig_fn.Returning(interp, func.data.FunctionData.passed_data, args);
}

pub fn callVoid(interp: *Interp, func: *Object, args: []const *Object) !void {
    const a = func.data;
    const b = a.FunctionData;
    const c = b.zig_fn;
    const d = c.Void;
    const e = b.passed_data;
    try d(interp, e, args);
}


fn preparePartialCall(interp: *Interp, data: *objtyp.ObjectData, args: []const *Object) ![]*Object {
    const all_args = try interp.object_allocator.alloc(*Object, data.ObjectArrayList.count() - 1 + args.len);
    errdefer interp.object_allocator.free(all_args);
    std.mem.copy(*Object, all_args, data.ObjectArrayList.toSliceConst()[1..]);
    std.mem.copy(*Object, all_args[(data.ObjectArrayList.count() - 1)..], args);
    return all_args;
}

fn partialFnVoid(interp: *Interp, data: *objtyp.ObjectData, args: []const *Object) anyerror!void {
    const all_args = try preparePartialCall(interp, data, args);
    defer interp.object_allocator.free(all_args);
    try callVoid(interp, data.ObjectArrayList.at(0), all_args);
}

fn partialFnReturning(interp: *Interp, data: *objtyp.ObjectData, args: []const *Object) anyerror!*Object {
    const all_args = try preparePartialCall(interp, data, args);
    defer interp.object_allocator.free(all_args);
    return try callReturning(interp, data.ObjectArrayList.at(0), all_args);
}

pub fn newPartial(interp: *Interp, func: *Object, extra_args: []const *Object) !*Object {
    const zig_fn = switch(func.data.FunctionData.zig_fn) {
        Fn.Returning => Fn{ .Returning = partialFnReturning },
        Fn.Void => Fn{ .Void = partialFnVoid },
    };

    var arrlst = std.ArrayList(*Object).init(interp.object_allocator);
    errdefer arrlst.deinit();
    try arrlst.append(func);
    for (extra_args) |arg| {
        try arrlst.append(arg);
    }

    const res = try new(interp, "<partial>", zig_fn, objtyp.ObjectData{ .ObjectArrayList = arrlst });

    for (arrlst.toSliceConst()) |obj| {
        obj.incref();
    }
    return res;
}
