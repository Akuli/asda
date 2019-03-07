const std = @import("std");
const Interp = @import("interp.zig").Interp;
const Object = @import("objtyp.zig").Object;


fn objectPtrHash(ptr: *Object) u32 {
    // the rightmost bits are often used for alignment
    // let's throw them away for a better distribution
    var n: usize = @ptrToInt(ptr) >> 2;
    return @truncate(u32, n);
}

fn objectPtrEq(a: *Object, b: *Object) bool {
    return a == b;
}

// u32 is used in checkRefcounts()
const ObjectSet = std.HashMap(*Object, u32, objectPtrHash, objectPtrEq);


pub const GC = struct {
    all: ObjectSet,

    pub fn init(interp: *Interp) GC {
        return GC{ .all = ObjectSet.init(interp.object_allocator) };
    }

    pub fn onNewObject(self: *GC, obj: *Object) !void {
        const already_there = try self.all.put(obj, 0);
        std.debug.assert(already_there == null);
    }

    pub fn onRefcountZero(self: *GC, obj: *Object) void {
        const res = self.all.remove(obj);
        std.debug.assert(res != null);
    }

    pub fn onInterpreterExit(self: *GC) void {
        self.refcountDebug();
        self.destroyEverything();
        self.all.deinit();
    }

    // should be called only at exit
    fn refcountDebug(self: *GC) void {
        // figure out what the refcounts should be by destroying so that only refcounts change
        var it = self.all.iterator();
        while (it.next()) |kv| {
            kv.value = kv.key.refcount;
            kv.key.refcount = std.math.maxInt(u32);
        }

        it = self.all.iterator();
        while (it.next()) |kv| {
            kv.key.destroy(true, false);
        }

        var problems = false;
        it = self.all.iterator();
        while (it.next()) |kv| {
            const should_be = std.math.maxInt(u32) - kv.key.refcount;
            const actual = kv.value;
            if (actual != should_be) {
                if (!problems) {
                    std.debug.warn("*** refcount issues detected ***\n");
                    problems = true;
                }
                std.debug.warn("  {*}: refcount={} (should be {}), asda_type={}\n", kv.key, actual, should_be, @tagName(kv.key.asda_type.*));
            }
        }
    }

    fn destroyEverything(self: *GC) void {
        var it = self.all.iterator();
        while (it.next()) |kv| {
            kv.key.destroy(false, true);
        }
    }
};
