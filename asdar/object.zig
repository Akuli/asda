const std = @import("std");
const objects = @import("objects/index.zig");
const AllocError = std.mem.Allocator.Error;

pub const Type = struct {
    // optional to work around a bug, never actually null, use getMethods() to access this
    // https://github.com/ziglang/zig/issues/1914
    methods: ?[]*Object,

    pub fn init(methods: []*Object) Type {
        return Type{ .methods = methods };
    }

    pub fn getMethods(typ: *Type) []*Object {
        return typ.methods.?;
    }
};

// TODO: const some stuff
var object_type_value = Type.init([]*Object { });
pub const object_type = &object_type_value;

pub const ObjectData = struct {

    pub const Value = union(enum) {
        StringValue: objects.string.Data,
        NoData,
    };

    value: Value,

    pub fn destroy(self: ObjectData) void {
        switch(self.value) {
            ObjectData.Value.NoData => { },
            ObjectData.Value.StringValue => self.value.StringValue.destroy(),
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
    allocator: *std.mem.Allocator,
    data: ObjectData,

    pub fn init(allocator: *std.mem.Allocator, typ: *Type, data: ?ObjectData) AllocError!*Object {
        const obj = try allocator.create(Object);
        errdefer allocator.destroy(obj);

        obj.* = Object{
            .asda_type = typ,
            .refcount = 1,
            .allocator = allocator,
            .data = data orelse ObjectData{ .value = ObjectData.Value.NoData },
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
            this.allocator.destroy(this);
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
    assert(obj.asda_type.getMethods().len == 0);
}
