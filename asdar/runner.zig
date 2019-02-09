const std = @import("std");
const Object = @import("objtyp.zig").Object;
const bcreader = @import("bcreader.zig");
const builtins = @import("builtins.zig");
const objects = @import("objects/index.zig");

const Scope = struct {
    allocator: *std.mem.Allocator,   // for creating subscopes
    local_vars: []const ?*Object,
    parent_scopes: []*Scope,
    free_local_vars_and_parent_scopes: bool,

    fn initGlobal(allocator: *std.mem.Allocator) Scope {
        return Scope{
            .allocator = allocator,
            .local_vars = builtins.builtin_array[0..],
            .parent_scopes = []*Scope{ },
            .free_local_vars_and_parent_scopes = false,
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
            .free_local_vars_and_parent_scopes = true,
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
        if (self.free_local_vars_and_parent_scopes) {
            self.allocator.free(self.local_vars);
            self.allocator.free(self.parent_scopes);
        }
    }
};

test "very basic scope creating" {
    const assert = std.debug.assert;

    var global_scope = Scope.initGlobal(std.heap.c_allocator);
    defer global_scope.destroy();
    var file_scope = try global_scope.initSub(3);
    defer file_scope.destroy();

    assert(global_scope.parent_scopes.len == 0);
    assert(file_scope.parent_scopes.len == 1);
    assert(file_scope.parent_scopes[0] == &global_scope);
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
                    const scope = self.scope.getForLevel(vardata.level);
                    const obj = scope.local_vars[vardata.index].?;
                    try self.stack.append(obj);
                    obj.incref();
                    i += 1;
                },
                bcreader.Op.Data.CallFunction => |calldata| {
                    const n = self.stack.count();
                    const args = self.stack.toSliceConst()[(n - calldata.nargs)..n];
                    const func = self.stack.at(n - calldata.nargs - 1);
                    defer {
                        for (args) |arg| {
                            arg.decref();
                        }
                        func.decref();

                        if (calldata.returning) {
                            // n: number of things in the stack initially
                            // -calldata.nargs: arguments popped from stack
                            // -1: func was popped from stack
                            // +1: return value pushed to stack
                            self.stack.shrink(n - calldata.nargs - 1 + 1);
                        } else {
                            // same as above but with no return value pushed
                            self.stack.shrink(n - calldata.nargs - 1);
                        }
                    }

                    std.debug.assert(args.len == calldata.nargs);
                    if (calldata.returning) {
                        std.debug.panic("not implemented yet :(");
                    } else {
                        try objects.function.callVoid(func, args);
                    }
                    i += 1;
                },
                bcreader.Op.Data.Constant => |obj| {
                    try self.stack.append(obj);
                    obj.incref();
                    i += 1;
                },
            }
        }

        std.debug.assert(self.stack.count() == 0);
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


pub fn runFile(allocator: *std.mem.Allocator, code: bcreader.Code) !void {
    var global_scope = Scope.initGlobal(allocator);
    defer global_scope.destroy();
    var file_scope = try global_scope.initSub(code.nlocalvars);
    defer file_scope.destroy();

    var runner = Runner.init(allocator, code.ops, &file_scope);
    defer runner.destroy();

    const result = try runner.run();
    std.debug.assert(result == RunResult.DidntReturn);
}
