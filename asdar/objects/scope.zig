// this is an object because:
//    * function objects have a definition scope, and multiple functions may
//      have the same definition scope
//    * scopes can be created at runtime
//    * a scope has to be destroyed when no more functions defined in it exist
//
// from this you can see that scopes must be reference counted anyway, and
// objects already implement reference counting

const std = @import("std");
const builtins = @import("../builtins.zig");
const Interp = @import("../interp.zig").Interp;
const objtyp = @import("../objtyp.zig");
const Object = objtyp.Object;


pub const Data = struct {
    interp: *Interp,
    local_vars: []?*Object,
    parent_scopes: []*Object,    // micro-optimization, see getForLevel

    fn initGlobal(interp: *Interp) !Data {
        const locals = try std.mem.dupe(interp.object_allocator, ?*Object, builtins.object_array[0..]);
        errdefer interp.object_allocator.free(locals);
        const scopes = try interp.object_allocator.alloc(*Object, 0);
        errdefer interp.object_allocator.free(scopes);

        for (locals) |obj| {
            obj.?.incref();
        }
        return Data{
            .interp = interp,
            .local_vars = locals,
            .parent_scopes = scopes,
        };
    }

    fn initSub(parent: *Object, nlocals: u16) !Data {
        const parentdata = parent.data.ScopeData;

        const locals = try parentdata.interp.object_allocator.alloc(?*Object, nlocals);
        errdefer parentdata.interp.object_allocator.free(locals);
        for (locals) |*obj| {
            obj.* = null;
        }

        const parents = try parentdata.interp.object_allocator.alloc(*Object, parentdata.parent_scopes.len + 1);
        errdefer parentdata.interp.object_allocator.free(parents);
        std.mem.copy(*Object, parents, parentdata.parent_scopes);
        parents[parentdata.parent_scopes.len] = parent;
        for (parents) |obj| {
            obj.incref();
        }

        return Data{
            .interp = parentdata.interp,
            .local_vars = locals,
            .parent_scopes = parents,
        };
    }

    pub fn destroy(self: Data, decref_refs: bool, free_nonrefs: bool) void {
        if (decref_refs) {
            for (self.local_vars) |obj| {
                if (obj != null) {
                    obj.?.decref();
                }
            }
            for (self.parent_scopes) |obj| {
                obj.decref();
            }
        }
        if (free_nonrefs) {
            self.interp.object_allocator.free(self.local_vars);
            self.interp.object_allocator.free(self.parent_scopes);
        }
    }
};

var type_value = objtyp.Type.init([]objtyp.Attribute { });
pub const typ = &type_value;

pub fn createGlobal(interp: *Interp) !*Object {
    const data = try Data.initGlobal(interp);
    errdefer data.destroy(true, true);
    return try Object.init(interp, typ, objtyp.ObjectData{ .ScopeData = data });
}

pub fn createSub(parent: *Object, nlocals: u16) !*Object {
    const data = try Data.initSub(parent, nlocals);
    errdefer data.destroy(true, true);
    return try Object.init(parent.data.ScopeData.interp, typ, objtyp.ObjectData{ .ScopeData = data });
}

pub fn getForLevel(scope: *Object, level: u16) *Object {
    const data = scope.data.ScopeData;
    var result: *Object = undefined;
    if (level == data.parent_scopes.len) {
        result = scope;
    } else {
        std.debug.assert(level < data.parent_scopes.len);
        result = data.parent_scopes[level];
    }

    result.incref();
    return result;
}

pub fn getLocalVars(scope: *Object) []?*Object {
    return scope.data.ScopeData.local_vars;
}


test "scope object creating and getForLevel" {
    var interp: Interp = undefined;
    try interp.init();
    defer interp.deinit();

    const global_scope = try createGlobal(&interp);
    defer global_scope.decref();
    const file_scope = try createSub(global_scope, 3);
    defer file_scope.decref();

    std.debug.assert(global_scope.data.ScopeData.parent_scopes.len == 0);
    std.debug.assert(file_scope.data.ScopeData.parent_scopes.len == 1);
    std.debug.assert(file_scope.data.ScopeData.parent_scopes[0] == global_scope);

    const a = getForLevel(global_scope, 0);
    defer a.decref();
    const b = getForLevel(file_scope, 0);
    defer b.decref();
    const c = getForLevel(file_scope, 1);
    defer c.decref();
    std.debug.assert(a == global_scope);
    std.debug.assert(b == global_scope);
    std.debug.assert(c == file_scope);
}
