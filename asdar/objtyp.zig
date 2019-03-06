// Object and Type

const std = @import("std");
const bcreader = @import("bcreader.zig");
const Interp = @import("interp.zig").Interp;
const objects = @import("objects/index.zig");
const runner = @import("runner.zig");

pub const BasicType = struct {
    // optional to work around a bug, never actually null, use getMethods() to access this
    // https://github.com/ziglang/zig/issues/1914
    methods: ?[]*Object,

    pub fn init(methods: []*Object) BasicType {
        return BasicType{ .methods = methods };
    }
};

pub const Type = union(enum) {
    Basic: BasicType,
    Function: objects.function.FunctionType,
};

pub fn getMethods(typ: *Type) []*Object{
    return switch(typ.*) {
        Type.Basic => |basictype| basictype.methods.?,
        Type.Function => []*Object{ },
    };
}

// TODO: const some stuff
var object_type_value = Type{ .Basic = BasicType.init([]*Object { }) };
pub const object_type = &object_type_value;

// used for arbitrary data outside this file, too
pub const ObjectData = union(enum) {
    StringData: objects.string.Data,
    FunctionData: objects.function.Data,
    ScopeData: objects.scope.Data,
    AsdaFunctionState: runner.AsdaFunctionState,
    NoData,

    pub fn destroy(self: ObjectData) void {
        switch(self) {
            ObjectData.NoData => { },

            // combining these into one makes the compiled executable segfault
            ObjectData.FunctionData => |val| val.destroy(),
            ObjectData.AsdaFunctionState => |val| val.destroy(),
            ObjectData.ScopeData => |val| val.destroy(),
            ObjectData.StringData => |val| val.destroy(),
        }
    }
};

test "ObjectData" {
    const objData = ObjectData{ .NoData = void{} };
    defer objData.destroy();
}

pub const Object = struct {
    asda_type: *Type,
    refcount: u32,     // TODO: use an atomic?
    interp: ?*Interp,   // null for objects created at comptime
    data: ObjectData,

    // put the return value to a variable and use &that_variable everywhere
    pub fn initComptime(typ: *Type, data: ?ObjectData) Object {
        return Object{
            .asda_type = typ,
            .refcount = 1,
            .interp = null,
            .data = data orelse ObjectData{ .NoData = void{} },     // TODO: is this the best way to do this?
        };
    }

    pub fn init(interp: *Interp, typ: *Type, data: ?ObjectData) !*Object {
        const obj = try interp.object_allocator.create(Object);
        errdefer interp.object_allocator.destroy(obj);

        obj.* = Object{
            .asda_type = typ,
            .refcount = 1,
            .interp = interp,
            .data = data orelse ObjectData{ .NoData = void{} },
        };
        return obj;
    }

    pub fn incref(self: *Object) void {
        self.refcount += 1;
    }

    pub fn decref(self: *Object) void {
        self.refcount -= 1;
        if (self.refcount == 0) {
            // this should never happen for comptime-created objects
            self.data.destroy();
            self.interp.?.object_allocator.destroy(self);
        }
    }
};

test "basic object creation" {
    const assert = std.debug.assert;
    var interp: Interp = undefined;
    interp.init();
    defer interp.deinit();

    const obj = try Object.init(&interp, object_type, null);
    defer obj.decref();

    assert(obj.refcount == 1);
    obj.incref();
    assert(obj.refcount == 2);
    obj.decref();
    assert(obj.refcount == 1);

    assert(obj.asda_type == object_type);
    assert(getMethods(obj.asda_type).len == 0);
}
