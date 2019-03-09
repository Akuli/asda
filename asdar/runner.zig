const std = @import("std");
const Interp = @import("interp.zig").Interp;
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const bcreader = @import("bcreader.zig");
const builtins = @import("builtins.zig");
const objects = @import("objects/index.zig");


const RunResult = union(enum) {
    Returned: ?*Object,  // value is null for void return
    DidntReturn,
};

const Runner = struct {
    interp: *Interp,
    scope: *Object,
    stack: std.ArrayList(*Object),    // TODO: give this a size hint calculated by the compiler
    ops: []bcreader.Op,

    fn init(interp: *Interp, ops: []bcreader.Op, scope: *Object) Runner {
        const stack = std.ArrayList(*Object).init(interp.object_allocator);
        errdefer stack.deinit();
        return Runner{ .scope = scope, .stack = stack, .ops = ops, .interp = interp };
    }

    fn debugDump(self: *const Runner) void {
        std.debug.warn("level {}\n", self.scope.data.ScopeData.parent_scopes.len);
        std.debug.warn("stack: ");
        for (self.stack.toSliceConst()) |obj| {
            std.debug.warn("{*} ", obj);
        }
        std.debug.warn("\n");

        std.debug.warn("local vars: ");
        for (self.scope.data.ScopeData.local_vars) |maybe_obj| {
            if (maybe_obj) |obj| {
                std.debug.warn("{*} ", obj);
            } else {
                std.debug.warn("null ");
            }
        }
        std.debug.warn("\n");
    }

    fn run(self: *Runner) !RunResult {
        var i: usize = 0;
        while (i < self.ops.len) {
            // uncomment to debug
            //self.debugDump();
            //std.debug.warn("doing next: {}\n", @tagName(self.ops[i].data));
            //std.debug.warn("\n");

            switch(self.ops[i].data) {
                bcreader.Op.Data.LookupVar => |vardata| {
                    const scope = objects.scope.getForLevel(self.scope, vardata.level);
                    defer scope.decref();

                    const obj = objects.scope.getLocalVars(scope)[vardata.index].?;
                    try self.stack.append(obj);
                    obj.incref();
                },
                bcreader.Op.Data.SetVar => |vardata| {
                    const scope = objects.scope.getForLevel(self.scope, vardata.level);
                    defer scope.decref();
                    if (objects.scope.getLocalVars(scope)[vardata.index]) |old_value| {
                        old_value.decref();
                    }
                    objects.scope.getLocalVars(scope)[vardata.index] = self.stack.pop();
                },
                bcreader.Op.Data.CreateFunction => |createdata| {
                    var the_fn: objects.function.Fn = undefined;
                    if (createdata.returning) {
                        the_fn = objects.function.Fn{ .Returning = asdaFunctionFnReturning };
                    } else {
                        the_fn = objects.function.Fn{ .Void = asdaFunctionFnVoid };
                    }

                    var func: *Object = undefined;
                    {
                        const data = objtyp.ObjectData{ .AsdaFunctionState = AsdaFunctionState{
                            .code = createdata.body,
                            .definition_scope = self.scope,
                        }};
                        data.AsdaFunctionState.definition_scope.incref();
                        errdefer data.destroy(true, true);

                        func = try objects.function.new(self.interp, createdata.name, the_fn, data);
                    }
                    errdefer func.decref();

                    try self.stack.append(func);
                },
                bcreader.Op.Data.CallFunction => |calldata| {
                    const n = self.stack.count();
                    const args = self.stack.toSliceConst()[(n - calldata.nargs)..n];
                    const func = self.stack.at(n - calldata.nargs - 1);

                    std.debug.assert(args.len == calldata.nargs);
                    if (calldata.returning) {
                        const ret = try objects.function.callReturning(self.interp, func, args);
                        self.stack.set(n - calldata.nargs - 1, ret);
                    } else {
                        try objects.function.callVoid(self.interp, func, args);
                    }

                    // nothing went wrong, have to decref all the things
                    // otherwise they are left in the stack and destroy() decrefs
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

                    for (args) |arg| {
                        arg.decref();
                    }
                    func.decref();
                },
                bcreader.Op.Data.Constant => |obj| {
                    try self.stack.append(obj);
                    obj.incref();
                },
                bcreader.Op.Data.Negation => {
                    const last = self.stack.count() - 1;
                    const old = self.stack.at(last);
                    defer old.decref();
                    const new = objects.boolean.fromZigBool(!objects.boolean.toZigBool(old));
                    self.stack.set(last, new);
                },
                bcreader.Op.Data.Return => |returns_a_value| {
                    var value: ?*Object = null;
                    if (returns_a_value) {
                        value = self.stack.pop();
                    }
                    std.debug.assert(self.stack.count() == 0);
                    return RunResult{ .Returned = value };
                },
                bcreader.Op.Data.PopOne => {
                    self.stack.pop().decref();
                },
                bcreader.Op.Data.DidntReturnError => {
                    std.debug.panic("a non-void function didn't return");
                },
                bcreader.Op.Data.LookupAttribute => |lookup| {
                    const last = self.stack.count() - 1;
                    const obj = self.stack.at(last);
                    const new = try lookup.typ.getAttribute(self.interp, obj, lookup.index);
                    obj.decref();
                    self.stack.set(last, new);
                },
                bcreader.Op.Data.JumpIf => {},
            }

            switch(self.ops[i].data) {
                bcreader.Op.Data.JumpIf => |jmp| {
                    const cond = self.stack.pop();
                    defer cond.decref();
                    i = if(objects.boolean.toZigBool(cond)) jmp else i+1;
                },
                else => i += 1,
            }
        }

        std.debug.assert(self.stack.count() == 0);
        return RunResult{ .DidntReturn = void {} };
    }

    fn destroy(self: Runner) void {
        var it = self.stack.iterator();
        while (it.next()) |obj| {
            obj.decref();
        }
        self.stack.deinit();
    }
};


// passed to functions defined in asda
pub const AsdaFunctionState = struct {
    code: bcreader.Code,
    definition_scope: *Object,

    pub fn destroy(self: AsdaFunctionState, decref_refs: bool, free_nonrefs: bool) void {
        // doesn't destroy the code because that's allocated with interp.import_allocator
        if (decref_refs) {
            self.definition_scope.decref();
        }
    }
};

// TODO: less copy/pasta!
fn asdaFunctionFnReturning(interp: *Interp, data: *objtyp.ObjectData, args: []const *objtyp.Object) anyerror!*Object {
    const call_scope = try objects.scope.createSub(data.AsdaFunctionState.definition_scope, data.AsdaFunctionState.code.nlocalvars);
    defer call_scope.decref();

    var i: usize = 0;
    for (args) |arg| {
        objects.scope.getLocalVars(call_scope)[i] = arg;
        arg.incref();
        i += 1;
    }

    // data.AsdaFunctionState.code.nlocalvars
    var runner = Runner.init(interp, data.AsdaFunctionState.code.ops, call_scope);
    defer runner.destroy();

    const result = try runner.run();
    return result.Returned.?;
}

fn asdaFunctionFnVoid(interp: *Interp, data: *objtyp.ObjectData, args: []const *objtyp.Object) anyerror!void {
    const call_scope = try objects.scope.createSub(data.AsdaFunctionState.definition_scope, data.AsdaFunctionState.code.nlocalvars);
    defer call_scope.decref();

    var i: usize = 0;
    for (args) |arg| {
        objects.scope.getLocalVars(call_scope)[i] = arg;
        arg.incref();
        i += 1;
    }

    // data.AsdaFunctionState.code.nlocalvars
    var runner = Runner.init(interp, data.AsdaFunctionState.code.ops, call_scope);
    defer runner.destroy();

    const result = try runner.run();
    std.debug.assert(result.Returned == null);
}


pub fn runFile(interp: *Interp, code: bcreader.Code) !void {
    const global_scope = try objects.scope.createGlobal(interp);
    defer global_scope.decref();
    const file_scope = try objects.scope.createSub(global_scope, code.nlocalvars);
    defer file_scope.decref();

    var runner = Runner.init(interp, code.ops, file_scope);
    defer runner.destroy();

    const result = try runner.run();
    std.debug.assert(result == RunResult.DidntReturn);
}
