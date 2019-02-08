const std = @import("std");
const Object = @import("object.zig").Object;
const bcreader = @import("bcreader.zig");

const Scope = struct {
    allocator: *std.mem.Allocator,   // for creating subscopes
    localvars: []?*Object,
    parent_scopes: []*Scope,

    fn initGlobal(allocator: *std.mem.Allocator) Scope {
        // yes, the empty slices work with the destroy(), i asked on #zig on freenode
        //
        //  <Akuli> if i have: const lol = []*T{ };   what happens if i do
        //          some_allocator.free(lol)? is that guaranteed to do nothing?
        //  <emekankurumeh[m]> I think the problem would be with passing the
        //                     allocator memory it doesn't own.
        //  <Akuli> yes, i'm asking whether an empty slice is a special case
        //  <andrewrk> yes empty slice with undefined pointer can be safely
        //             passed to free
        return Scope{
            .allocator = allocator,
            .localvars = []*Object{ },
            .parent_scopes = []*Scope{ },
        };
    }

    fn initSub(parent: *Scope, nlocals: u16) !Scope {
        const locals = try parent.allocator.alloc(?*Object, nlocals);
        errdefer parent.allocator.free(locals);
        for (locals) |*obj| {
            obj.* = null;
        }

        const parents = try parent.allocator.alloc(*Scope, parent.parent_scopes.len + 1);
        errdefer parent.allocator.free(parents);
        std.mem.copy(*Scope, parents, parent.parent_scopes);
        parents[parent.parent_scopes.len] = parent;

        return Scope{
            .allocator = parent.allocator,
            .localvars = locals,
            .parent_scopes = parents,
        };
    }

    fn destroy(self: Scope) void {
        self.allocator.free(self.localvars);
        self.allocator.free(self.parent_scopes);
    }
};

test "very basic scope creation" {
    const assert = std.debug.assert;

    var objs = []?*Object{ null };
    const s = Scope{ .localvars = objs[0..], .parent_scopes = []Scope{ }};
    assert(s.localvars.len == 1);
    assert(s.parent_scopes.len == 0);
}

const RunResult = union(enum) {
    Returned: ?*Object,  // value is null for void return
    DidntReturn,
};

const Runner = struct {
    scope: *Scope,
    stack: std.ArrayList(*Object),    // TODO: use a fixed size array, calculate size in compiler
    ops: []bcreader.Op,

    fn init(allocator: *std.mem.Allocator, ops: []bcreader.Op, scope: *Scope) Runner {
        const stack = std.ArrayList(*Object).init(allocator);
        errdefer stack.deinit();
        return Runner{ .scope = scope, .stack = stack, .ops = ops };
    }

    fn run(self: *Runner) RunResult {
        var i: usize = 0;
        while (i < self.ops.len) : (i += 1) {
            std.debug.warn("Would do a thing\n");
        }
        return RunResult.DidntReturn;
    }

    fn destroy(self: Runner) void {
        self.stack.deinit();
    }
};


pub fn runFile(allocator: *std.mem.Allocator, code: bcreader.Code) !RunResult {
    var global_scope = Scope.initGlobal(allocator);
    defer global_scope.destroy();
    var file_scope = try global_scope.initSub(code.nlocalvars);
    defer file_scope.destroy();

    var runner = Runner.init(allocator, code.ops, &file_scope);
    defer runner.destroy();
    return runner.run();
}
