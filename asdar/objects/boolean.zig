const std = @import("std");
const assert = std.debug.assert;
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;


var type_value = objtyp.Type{ .Basic = objtyp.BasicType.init([]*Object { }) };
pub const typ = &type_value;

var true_value = Object.initComptime(typ, null);
var false_value = Object.initComptime(typ, null);
pub const TRUE = &true_value;
pub const FALSE = &false_value;

pub fn fromZigBool(b: bool) *Object {
    const res = if(b) TRUE else FALSE;
    res.incref();
    return res;
}

pub fn toZigBool(b: *Object) bool {
    return switch(b) {
        TRUE => true,
        FALSE => false,
        else => unreachable,
    };
}

test "fromZigBool" {
    const t = fromZigBool(true);
    defer t.decref();
    const f = fromZigBool(false);
    defer f.decref();

    assert(t == TRUE);
    assert(f == FALSE);
}

test "toZigBool" {
    assert(toZigBool(TRUE));
    assert(!toZigBool(FALSE));
}
