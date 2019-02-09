// Object and Type

const std = @import("std");
const objects = @import("objects/index.zig");

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

pub const ObjectData = union(enum) {
    StringValue: objects.string.Data,
    FunctionValue: objects.function.Data,
    NoData,

    pub fn destroy(self: ObjectData) void {
        switch(self) {
            ObjectData.NoData, ObjectData.FunctionValue => { },
            ObjectData.StringValue => |val| val.destroy(),
        }
    }
};

test "ObjectData" {
    const objData = ObjectData{ .value = ObjectData.Value.NoData };
    defer objData.destroy();
}

pub const Object = struct {
    asda_type: *Type,
    refcount: u32,     // TODO: use an atomic?
    allocator: ?*std.mem.Allocator,   // null for objects created at comptime
    data: ObjectData,

    // put the return value to a variable and use &that_variable everywhere
    pub fn initComptime(typ: *Type, data: ?ObjectData) Object {
        return Object{
            .asda_type = typ,
            .refcount = 1,
            .allocator = null,
            .data = data orelse ObjectData{ .NoData = void{} },     // TODO: is this the best way to do this?
        };
    }

    pub fn init(allocator: *std.mem.Allocator, typ: *Type, data: ?ObjectData) !*Object {
        const obj = try allocator.create(Object);
        errdefer allocator.destroy(obj);

        obj.* = Object{
            .asda_type = typ,
            .refcount = 1,
            .allocator = allocator,
            .data = data orelse ObjectData{ .NoData = void{} },
        };
        return obj;
    }

    pub fn incref(this: *Object) void {
        this.refcount += 1;
    }

    pub fn decref(this: *Object) void {
        this.refcount -= 1;
        if (this.refcount == 0) {
            this.data.destroy();
            (this.allocator orelse unreachable).destroy(this);
        }
    }
};

test "basic object creation" {
    const assert = std.debug.assert;

    const obj = try Object.init(std.heap.c_allocator, object_type, null);
    defer obj.decref();

    assert(obj.refcount == 1);
    obj.incref();
    assert(obj.refcount == 2);
    obj.decref();
    assert(obj.refcount == 1);

    assert(obj.asda_type == object_type);
    assert(getMethods(obj.asda_type).len == 0);
}
