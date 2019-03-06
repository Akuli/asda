const std = @import("std");
const GC = @import("gc.zig").GC;


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

    pub fn init(self: *Interp) void {
        self.object_allocator = std.heap.c_allocator;
        self.import_arena = std.heap.ArenaAllocator.init(std.heap.c_allocator);
        self.import_arena_allocator = &self.import_arena.allocator;
        self.gc = GC.init(self);
    }

    pub fn deinit(self: *Interp) void {
        self.gc.onInterpreterExit();
        self.import_arena.deinit();
    }
};

test "interp creating and deleting" {
    var interp: Interp = undefined;
    interp.init();
    defer interp.deinit();

    const buf = try interp.import_arena_allocator.alloc(u8, 5);
    buf[0] = 'h';
    buf[1] = 'e';
    buf[2] = 'l';
    buf[3] = 'l';
    buf[4] = 'o';
}
