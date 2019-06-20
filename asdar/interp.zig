const std = @import("std");
const bcreader = @import("bcreader.zig");
const builtin = @import("builtin");
const GC = @import("gc.zig").GC;
const misc = @import("misc.zig");
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const objects = @import("objects/index.zig");
const runner = @import("runner.zig");


pub const ImportErrorInfo = struct {
    errorByte: ?u8,
    path: ?[]const u8,
};

pub const Module = struct {
    code: bcreader.Code,

    // currently this contains all local variables, but it works because the exports are first
    export_vars: []?*Object,

    fn destroy(self: Module, interp: *const Interp) void {
        for (self.export_vars) |objopt| {
            if (objopt) |obj| {
                obj.decref();
            }
        }
        interp.object_allocator.free(self.export_vars);
        self.code.destroy(true, true);
    }
};

pub const Interp = struct {
    // should be used for most allocations that can be initiated by the code being ran
    // e.g. when the user wants to create new objects
    pub object_allocator: *std.mem.Allocator,

    // mostly for import-time things
    // guaranteed to be an arena allocator, so allocated stuff don't need freeing
    // memory is freed when interpreter exits
    // that is, don't let the user allocate memory with this (e.g. in a loop)!
    pub import_arena_allocator: *std.mem.Allocator,

    import_arena: std.heap.ArenaAllocator,
    pub gc: GC,
    pub modules: std.AutoHashMap([]const u8, Module),   // use misc.normcasePath for all the keys
    pub global_scope: *Object,

    pub fn init(self: *Interp) !void {
        self.object_allocator = std.heap.c_allocator;
        self.import_arena = std.heap.ArenaAllocator.init(std.heap.c_allocator);
        self.import_arena_allocator = &self.import_arena.allocator;
        self.gc = GC.init(self);
        self.global_scope = try objects.scope.createGlobal(self);
        self.modules = std.AutoHashMap([]const u8, Module).init(self.import_arena_allocator);
    }

    pub fn deinit(self: *Interp) void {
        while (self.modules.iterator().next()) |kv| {        // TODO: optimize this
            kv.value.destroy(self);
            _ = self.modules.remove(kv.key);
        }
        self.modules.deinit();

        self.global_scope.decref();
        self.gc.onInterpreterExit();
        self.import_arena.deinit();
    }

    pub fn import(self: *Interp, raw_path: []const u8, errorinfo: *ImportErrorInfo) !void {
        const tmp_path = try std.os.path.resolve(self.object_allocator, []const []const u8 {raw_path});
        defer self.object_allocator.free(tmp_path);
        misc.normcasePath(tmp_path);

        // avoid using import_arena_allocator (would leak memory)
        if (self.modules.get(tmp_path)) |_| {
            return;
        }

        const nice_path = try std.mem.dupe(self.import_arena_allocator, u8, tmp_path);
        try self.importFromNicePath(nice_path, errorinfo);
    }

    fn importFromNicePath(self: *Interp, nice_path: []const u8, errorinfo: *ImportErrorInfo) anyerror!void {
        errorinfo.path = nice_path;
        if (self.modules.get(nice_path)) |_| {
            return;
        }

        const f = try std.os.File.openRead(nice_path);
        defer f.close();
        const stream = &f.inStream().stream;
        var reader = bcreader.BytecodeReader.init(self, nice_path, stream, &errorinfo.errorByte);

        try reader.readAsdaBytes();
        for (try reader.readImports()) |imp| {
            try self.importFromNicePath(imp, errorinfo);
            errorinfo.path = nice_path;
        }

        const code = try reader.readCodePart();
        errdefer code.destroy(true, true);

        const scope = try objects.scope.createSub(self.global_scope, code.nlocalvars);
        defer scope.decref();   // TODO: check that functions hold reference to their globals when needed

        try runner.runFile(self, code, scope);

        // not all local vars are exported, but this works anyway because the exported vars are first
        const exported_vars_and_stuff = objects.scope.getLocalVarsOwned(scope);
        const already_there = try self.modules.put(nice_path, Module{
            .code = code,
            .export_vars = exported_vars_and_stuff,
        });
        std.debug.assert(already_there == null);
    }
};

test "interp creating and deleting" {
    var interp: Interp = undefined;
    try interp.init();
    defer interp.deinit();

    const buf = try interp.import_arena_allocator.alloc(u8, 5);
    buf[0] = 'h';
    buf[1] = 'e';
    buf[2] = 'l';
    buf[3] = 'l';
    buf[4] = 'o';
}
