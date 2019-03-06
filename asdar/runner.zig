const std = @import("std");
const Interp = @import("interp.zig").Interp;
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const bcreader = @import("bcreader.zig");
const builtins = @import("builtins.zig");
const objects = @import("objects/index.zig");


fn asdaFunctionFnReturning(interp: *Interp, data: *objtyp.ObjectData, args: []const *objtyp.Object) anyerror!*Object {
    std.debug.assert(args.len == 1);
    args[0].incref();
    return args[0];
}

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

    // yes this is needed, otherwise doesn't compile
    fn runHelper() RunResult {
        return RunResult.DidntReturn;
    }

    fn run(self: *Runner) !RunResult {
        var i: usize = 0;
        while (i < self.ops.len) {
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
                    objects.scope.getLocalVars(scope)[vardata.index] = self.stack.pop();
                },
                bcreader.Op.Data.CreateFunction => |createdata| {
                    std.debug.assert(createdata.typ.Function.returntype != null);     // TODO
                    const the_fn = objects.function.Fn{ .Returning = asdaFunctionFnReturning };

                    var func: *Object = undefined;
                    {
                        const data = try self.interp.object_allocator.create(objtyp.ObjectData);
                        errdefer data.destroy();
                        data.* = objtyp.ObjectData{ .BcreaderCode = createdata.body };
                        func = try objects.function.new(self.interp, createdata.name, createdata.typ, the_fn, data);
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
