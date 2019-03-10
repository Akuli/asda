const std = @import("std");
const builtin = @import("builtin");
const GC = @import("gc.zig").GC;
const import = @import("import.zig");
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const objects = @import("objects/index.zig");


fn normcaseWindowsPath(path: []u8) void {
    for (path) |c, i| {
        // TODO: also lowercase non-ascii characters
        path[i] = if ('A' <= c and c <= 'Z') c+('a'-'A') else if (c == '/') '\\' else c;
    }
}
fn normcasePosixPath(path: []u8) void { }
const normcasePath = if (builtin.os == builtin.Os.windows) normcaseWindowsPath else normcasePosixPath;

test "normcaseWindowsPath" {
    const assert = std.debug.assert;
    const normalized = try normcaseWindowsPath(std.heap.c_allocator, "ABCXYZabcxyz/\\:.");
    defer std.heap.c_allocator.free(normalized);
    assert(std.mem.eql(u8, normalized, "abcxyzabcxyz/\\:."));   // zig handles forwardslash to backslash conversion
}


const ImportErrorInfo = struct {
    errorByte: ?u8,
    path: ?[]const u8,
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
    pub modules: std.AutoHashMap([]const u8, *Object),
    pub global_scope: *Object,

    // TODO: replace with real exceptions
    pub last_import_error: ImportErrorInfo,

    pub fn init(self: *Interp) !void {
        self.last_import_error = ImportErrorInfo{ .errorByte = null, .path = null };
        self.object_allocator = std.heap.c_allocator;
        self.import_arena = std.heap.ArenaAllocator.init(std.heap.c_allocator);
        self.import_arena_allocator = &self.import_arena.allocator;
        self.gc = GC.init(self);
        self.global_scope = try objects.scope.createGlobal(self);
        self.modules = std.AutoHashMap([]const u8, *Object).init(self.import_arena_allocator);
    }

    pub fn deinit(self: *Interp) void {
        while (self.modules.iterator().next()) |kv| {        // TODO: optimize this
            if (kv.value.asda_type.attributes) |attrs| {
                for (attrs) |attr| {
                    std.debug.assert(!attr.is_method);
                    attr.value.decref();
                }
            }
            kv.value.decref();
            _ = self.modules.remove(kv.key);
        }
        self.modules.deinit();

        self.global_scope.decref();
        self.gc.onInterpreterExit();
        self.import_arena.deinit();
    }

    // on success:
    //   * self.last_import_error.errorByte is set to null
    //   * self.last_import_error.path is left to the cleaned-up path, non-null
    fn getModuleInternal(self: *Interp, raw_path: []const u8) !*Object {
        self.last_import_error.errorByte = null;
        self.last_import_error.path = null;

        const tmp_path = try std.os.path.resolve(self.object_allocator, []const []const u8 {raw_path});
        defer self.object_allocator.free(tmp_path);
        normcasePath(tmp_path);

        var module: *Object = undefined;
        if (self.modules.get(tmp_path)) |kv| {
            self.last_import_error.path = kv.key;
            module = kv.value;
        } else {
            const path = try std.mem.dupe(self.import_arena_allocator, u8, tmp_path);
            self.last_import_error.path = path;

            const typ = try self.import_arena_allocator.create(objtyp.Type);
            typ.* = objtyp.Type.init(null);

            module = try Object.init(self, typ, null);
            errdefer module.decref();

            const already_there = try self.modules.put(path, module);
            std.debug.assert(already_there == null);
        }

        module.incref();
        return module;
    }

    pub fn getModule(self: *Interp, raw_path: []const u8) !*Object {
        const res = try self.getModuleInternal(raw_path);
        self.last_import_error.errorByte = null;
        self.last_import_error.path = null;
        return res;
    }

    // some kind of cycle going on, doesn't compile without anyerror
    pub fn loadModule(self: *Interp, raw_path: []const u8) anyerror!*Object {
        const mod = try self.getModuleInternal(raw_path);
        errdefer mod.decref();
        if (mod.asda_type.attributes != null) {
            // loaded already
            return mod;
        }

        try import.loadModule(self, self.last_import_error.path.?, mod);

        self.last_import_error.errorByte = null;
        self.last_import_error.path = null;
        return mod;
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
