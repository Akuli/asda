const std = @import("std");
const Object = @import("object.zig").Object;
const bcreader = @import("bcreader.zig");

const Scope = struct {
    allocator: *std.mem.Allocator,   // for creating subscopes
    local_vars: []?*Object,
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
            .local_vars = []*Object{ },
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
            .local_vars = locals,
            .parent_scopes = parents,
        };
    }

    fn getForLevel(self: *Scope, level: u16) *Scope {
        if (level == self.parent_scopes.len) {
            return self;
        }
        std.debug.assert(level < self.parent_scopes.len);
        return self.parent_scopes[level];
    }

    fn destroy(self: Scope) void {
        self.allocator.free(self.local_vars);
        self.allocator.free(self.parent_scopes);
    }
};

test "very basic scope creation" {
    const assert = std.debug.assert;

    var objs = []?*Object{ null };
    const s = Scope{ .local_vars = objs[0..], .parent_scopes = []Scope{ }};
    assert(s.local_vars.len == 1);
    assert(s.parent_scopes.len == 0);
}

const RunResult = union(enum) {
    Returned: ?*Object,  // value is null for void return
    DidntReturn,
};

const Runner = struct {
    scope: *Scope,
    stack: std.ArrayList(*Object),    // TODO: give this a size hint calculated by the compiler
    ops: []bcreader.Op,

    fn init(allocator: *std.mem.Allocator, ops: []bcreader.Op, scope: *Scope) Runner {
        const stack = std.ArrayList(*Object).init(allocator);
        errdefer stack.deinit();
        return Runner{ .scope = scope, .stack = stack, .ops = ops };
    }

    // yes this is needed, otherwise doesn't compile
    fn runHelper() RunResult {
        return RunResult.DidntReturn;
    }

    fn run(self: *Runner) !RunResult {
        var i: usize = 0;
        while (i < self.ops.len) {
            switch(self.ops[i].data) {
                bcreader.Op.Data.LookupVar => |vardata| {
                    std.debug.warn("Looking up a var lol\n");
                    //const scope = self.scope.getForLevel(vardata.level);
                    //const obj = scope.local_vars[vardata.index].?;
                    //try self.stack.append(obj);
                    //obj.incref();
                    i += 1;
                },
                bcreader.Op.Data.CallFunction => {
                    std.debug.warn("Calling a function löl\n");
                    i += 1;
                },
                bcreader.Op.Data.Constant => |obj| {
                    try self.stack.append(obj);
                    obj.incref();
                    i += 1;
                },
            }
        }
        return Runner.runHelper();
    }

    fn destroy(self: Runner) void {
        var it = self.stack.iterator();
        while (it.next()) |obj| {
            obj.decref();
        }
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
    return (try runner.run());
}
