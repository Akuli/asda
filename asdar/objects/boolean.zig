const std = @import("std");
const assert = std.debug.assert;
const Type = @import("../object.zig").Type;
const Object = @import("../object.zig").Object;
const ObjectData = @import("../object.zig").ObjectData;


var type_value = Type.init([]*Object { });
pub const typ = &type_value;

const no_data = ObjectData{ .value = ObjectData.Value.NoData };
var true_value = Object.initComptime(typ, no_data);
var false_value = Object.initComptime(typ, no_data);
pub const TRUE = &true_value;
pub const FALSE = &false_value;

pub fn fromZigBool(b: bool) *Object {
    const res = if(b) TRUE else FALSE;
    res.incref();
    return res;
}

test "fromZigBool" {
    const t = fromZigBool(true);
    defer t.decref();
    const f = fromZigBool(false);
    defer f.decref();

    assert(t == TRUE);
    assert(f == FALSE);
}
