const std = @import("std");
const bcreader = @import("bcreader.zig");
const GC = @import("gc.zig").GC;
const Interp = @import("interp.zig").Interp;
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const objects = @import("objects/index.zig");
const runner = @import("runner.zig");


pub const Data = struct {
    code: bcreader.Code,

    pub fn destroy(self: Data, decref_refs: bool, free_nonrefs: bool) void {
        self.code.destroy(decref_refs, free_nonrefs);
    }
};

// uses interp.last_import_error.errorByte, but NOT interp.last_import_error.path
pub fn loadModule(interp: *Interp, path: []const u8, module: *Object) !void {
    const code = blk: {
        const f = try std.os.File.openRead(path);
        defer f.close();

        const stream = &f.inStream().stream;
        break :blk try bcreader.readByteCode(interp, path, stream, &interp.last_import_error.errorByte);
    };
    errdefer code.destroy(true, true);

    const scope = try objects.scope.createSub(interp.global_scope, code.nlocalvars);
    defer scope.decref();

    try runner.runFile(interp, code, scope);

    const attrs = try interp.import_arena_allocator.alloc(objtyp.Attribute, scope.data.ScopeData.local_vars.len);
    errdefer interp.import_allocator.free(attrs);
    for (scope.data.ScopeData.local_vars) |obj, i| {
        attrs[i] = objtyp.Attribute{ .is_method = false, .value = obj.? };
        obj.?.incref();
    }

    std.debug.assert(module.asda_type.attributes == null);
    module.data = objtyp.ObjectData{ .ModuleData = Data{ .code = code }};
    module.asda_type.attributes = attrs;
}
