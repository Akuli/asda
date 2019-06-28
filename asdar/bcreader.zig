// bytecode reader

const std = @import("std");
const builtins = @import("builtins.zig");
const Interp = @import("interp.zig").Interp;
const misc = @import("misc.zig");
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const objects = @import("objects/index.zig");

use @cImport(@cInclude("gmp.h"));

const StreamType = std.io.InStream(std.os.File.InStream.Error);

const SET_LINENO: u8 = 'L';
const CREATE_FUNCTION: u8 = 'f';    // also used in types
const LOOKUP_VAR: u8 = 'v';
const SET_VAR: u8 = 'V';
const STR_CONSTANT: u8 = '"';
const NON_NEGATIVE_INT_CONSTANT: u8 = '1';
const NEGATIVE_INT_CONSTANT: u8 = '2';
const TRUE_CONSTANT: u8 = 'T';
const FALSE_CONSTANT: u8 = 'F';
const LOOKUP_METHOD: u8 = '.';
const LOOKUP_FROM_MODULE: u8 = 'm';
const CALL_VOID_FUNCTION: u8 = '(';
const CALL_RETURNING_FUNCTION: u8 = ')';
const STR_JOIN: u8 = 'j';
const POP_ONE: u8 = 'P';
const VOID_RETURN: u8 = 'r';
const VALUE_RETURN: u8 = 'R';
const DIDNT_RETURN_ERROR: u8 = 'd';
const YIELD: u8 = 'Y';
const NEGATION: u8 = '!';
const JUMP_IF: u8 = 'J';
const END_OF_BODY: u8 = 'E';
const IMPORT_SECTION: u8 = 'i';

const PLUS: u8 = '+';
const MINUS: u8 = '-';
const PREFIX_MINUS: u8 = '_';
const TIMES: u8 = '*';
const EQUAL: u8 = '=';

const TYPE_BUILTIN: u8 = 'b';
const TYPE_GENERATOR: u8 = 'G';
const TYPE_VOID: u8 = 'v';


pub const Op = struct {
    pub const VarData = struct{ level: u8, index: u16 };
    pub const CallFunctionData = struct{ returning: bool, nargs: u8 };
    pub const LookupMethodData = struct{ typ: *objtyp.Type, index: u16 };
    pub const CreateFunctionData = struct{ returning: bool, body: Code };
    pub const LookupFromModuleData = struct{ array: []?*Object, index: u16 };

    pub const Data = union(enum) {
        LookupVar: VarData,
        SetVar: VarData,
        LookupMethod: LookupMethodData,
        LookupFromModule: LookupFromModuleData,
        CreateFunction: CreateFunctionData,
        CallFunction: CallFunctionData,
        Constant: *Object,
        Negation: void,
        Add: void,
        Sub: void,
        Mul: void,
        Equal: void,
        PopOne: void,
        JumpIf: u16,
        Return: bool,   // true to return a value, false for void return
        DidntReturnError: void,
        StrJoin: u16,   // TODO: should this be bigger??!
        PrefixMinus: void,

        pub fn destroy(self: Op.Data, decref_refs: bool, free_nonrefs: bool) void {
            switch(self) {
                Op.Data.Constant => |obj| if (decref_refs) obj.decref(),
                Op.Data.CreateFunction => |data| data.body.destroy(decref_refs, free_nonrefs),
                else => {},
            }
        }
    };

    lineno: u32,
    data: Data,

    pub fn destroy(op: Op, decref_refs: bool, free_nonrefs: bool) void {
        op.data.destroy(decref_refs, free_nonrefs);
    }
};

pub const Code = struct {
    ops: []Op,      // allocated with import_arena_allocator
    nlocalvars: u16,

    pub fn destroy(self: Code, decref_refs: bool, free_nonrefs: bool) void {
        for (self.ops) |op| {
            op.destroy(decref_refs, free_nonrefs);
        }
    }

    pub fn debugDump(self: Code) void {
        for (self.ops) |op| {
            std.debug.warn("{}  ", op.lineno);
            switch(op.data) {
                Op.Data.LookupVar => |vardata| std.debug.warn("LookupVar: level={}, index={}\n", vardata.level, vardata.index),
                Op.Data.CallFunction => |funcdata| std.debug.warn("CallFunction: returning={}, nargs={}\n", funcdata.returning, funcdata.nargs),
                Op.Data.Constant => |obj| std.debug.warn("Constant: {}, refcount={}\n", &obj, obj.refcount),
            }
        }
    }
};

pub const BytecodeReader = struct {
    interp: *Interp,
    in: *StreamType,
    inpath_dirname: []const u8,
    lineno: u32,
    errorByte: *?u8,
    import_paths: ?[][]u8,

    pub fn init(interp: *Interp, inpath: []const u8, in: *StreamType, errorByte: *?u8) BytecodeReader {
        return BytecodeReader{
            .interp = interp,
            .inpath_dirname = std.os.path.dirname(inpath).?,
            .in = in,
            .lineno = 1,
            .errorByte = errorByte,
            .import_paths = null,
        };
    }

    fn readString(self: *BytecodeReader) ![]u8 {
        const len = try self.in.readIntLittle(u32);
        // TODO: use a better allocator? this is usually temporary
        const result = try self.interp.import_arena_allocator.alloc(u8, len);

        try self.in.readNoEof(result);
        return result;
    }

    fn readPath(self: *BytecodeReader, normcase: bool) ![]u8 {
        const relative = try self.readString();
        for (relative) |c, i| {
            if (c == '/') {
                relative[i] = std.os.path.sep;
            }
        }

        const result = try std.os.path.resolve(self.interp.import_arena_allocator, []const []const u8 { self.inpath_dirname, relative });
        if (normcase) {
            misc.normcasePath(result);
        }
        return result;
    }

    // anyerror is needed because this calls itself, the compiler gets confused without anyerror
    fn readType(self: *BytecodeReader, firstByte: ?u8) anyerror!?*objtyp.Type {
        const magic = firstByte orelse try self.in.readByte();

        switch(magic) {
            TYPE_BUILTIN => {
                const index = try self.in.readIntLittle(u8);
                return builtins.type_array[index];
            },
            CREATE_FUNCTION => {
                const returning = ((try self.readType(null)) != null);

                const nargs = try self.in.readIntLittle(u8);
                var i: usize = 0;
                while (i < nargs) : (i += 1) {
                    const typ = try self.readType(null);
                    std.debug.assert(typ != null);
                    // the type isn't needed for anything, at least not yet
                }

                if (returning) {
                    return objects.function.returning_type;
                }
                return objects.function.void_type;
            },
            TYPE_VOID => {
                return null;
            },
            else => {
                self.errorByte.* = magic;
                return error.BytecodeInvalidTypeByte;
            },
        }
    }

    pub fn readAsdaBytes(self: *BytecodeReader) !void {
        var buf = []u8{ 0, 0, 0, 0 };
        if( (4 != try self.in.read(buf[0..])) or !std.mem.eql(u8, buf, "asda") ) {
            return error.BytecodeNotAnAsdaFile;
        }
    }

    // allocates with import_arena_allocator (no need to free results)
    pub fn readImports(self: *BytecodeReader) ![][]u8 {
        const byte = try self.in.readByte();
        if (byte != IMPORT_SECTION) {
            self.errorByte.* = byte;
            return error.BytecodeBeginsUnexpectedly;
        }

        const npaths = try self.in.readIntLittle(u16);
        const paths = try self.interp.import_arena_allocator.alloc([]u8, npaths);
        for (paths) |*ptr| {
            // normcased to make the paths valid keys for interp.modules
            ptr.* = try self.readPath(true);
        }
        self.import_paths = paths;
        return paths;
    }

    fn readBody(self: *BytecodeReader) anyerror!Code {
        const nlocals = try self.in.readIntLittle(u16);

        var ops = std.ArrayList(Op).init(self.interp.import_arena_allocator);
        errdefer {
            var it = ops.iterator();
            while (it.next()) |op| {
                op.destroy(true, true);
            }
            // no need to deinit the arraylist because it's allocated with import_arena_allocator
        }

        while (true) {
            var opbyte = try self.in.readByte();
            if (opbyte == SET_LINENO) {
                self.lineno = try self.in.readIntLittle(u32);
                opbyte = try self.in.readByte();
                if (opbyte == SET_LINENO) {
                    return error.BytecodeRepeatedLineno;
                }
            }

            const opdata = switch(opbyte) {
                END_OF_BODY => break,    // breaks while(true), does nothing to switch(opbyte)
                STR_CONSTANT => blk: {
                    const value = try self.readString();
                    const obj = try objects.string.newFromUtf8(self.interp, value);
                    break :blk Op.Data{ .Constant = obj };
                },
                TRUE_CONSTANT, FALSE_CONSTANT => blk: {
                    const obj = switch(opbyte) {
                        TRUE_CONSTANT => objects.boolean.TRUE,
                        FALSE_CONSTANT => objects.boolean.FALSE,
                        else => unreachable,
                    };
                    obj.incref();
                    break :blk Op.Data{ .Constant = obj };
                },
                LOOKUP_VAR, SET_VAR => blk: {
                    const level = try self.in.readIntLittle(u8);
                    const index = try self.in.readIntLittle(u16);
                    const vardata = Op.VarData{ .level = level, .index = index };
                    break :blk switch(opbyte) {
                        LOOKUP_VAR => Op.Data{ .LookupVar = vardata },
                        SET_VAR => Op.Data{ .SetVar = vardata },
                        else => unreachable,
                    };
                },
                PREFIX_MINUS => Op.Data{ .PrefixMinus = void{} },      // TODO: is void{} best way?
                PLUS => Op.Data{ .Add = void{} },
                MINUS => Op.Data{ .Sub = void{} },
                TIMES => Op.Data{ .Mul = void{} },
                EQUAL => Op.Data{ .Equal = void{} },
                NEGATION => Op.Data{ .Negation = void{} },
                POP_ONE => Op.Data{ .PopOne = void{} },
                DIDNT_RETURN_ERROR => Op.Data{ .DidntReturnError = void{} },
                VOID_RETURN => Op.Data{ .Return = false },
                VALUE_RETURN => Op.Data{ .Return = true },
                JUMP_IF => Op.Data{ .JumpIf = try self.in.readIntLittle(u16) },
                STR_JOIN => Op.Data{ .StrJoin = try self.in.readIntLittle(u16) },
                CALL_VOID_FUNCTION, CALL_RETURNING_FUNCTION => blk: {
                    const ret = (opbyte == CALL_RETURNING_FUNCTION);
                    const nargs = try self.in.readIntLittle(u8);
                    break :blk Op.Data{ .CallFunction = Op.CallFunctionData{ .returning = ret, .nargs = nargs }};
                },
                CREATE_FUNCTION => blk: {
                    const typ = (try self.readType(CREATE_FUNCTION)).?;
                    const yields = switch(try self.in.readByte()) {
                        0 => false,
                        else => unreachable,    // TODO: yielding functions
                    };
                    const body = try self.readBody();
                    errdefer body.destroy();
                    break :blk Op.Data{ .CreateFunction = Op.CreateFunctionData{
                        .returning = (typ == objects.function.returning_type),
                        .body = body,
                    }};
                },
                NON_NEGATIVE_INT_CONSTANT => blk: {
                    const data = try self.readString();
                    const val = try objects.integer.newFromFunnyAsdaBytecodeNumberString(self.interp, data);
                    break :blk Op.Data{ .Constant = val };
                },
                NEGATIVE_INT_CONSTANT => blk: {
                    const data = try self.readString();
                    var val = try objects.integer.newFromFunnyAsdaBytecodeNumberString(self.interp, data);
                    try objects.integer.negateInPlace(&val);
                    break :blk Op.Data{ .Constant = val };
                },
                LOOKUP_METHOD => blk: {
                    const typ = (try self.readType(null)).?;
                    const i = try self.in.readIntLittle(u16);
                    break :blk Op.Data{ .LookupMethod = Op.LookupMethodData{ .typ = typ, .index = i }};
                },
                LOOKUP_FROM_MODULE => blk: {
                    const path = self.import_paths.?[try self.in.readIntLittle(u16)];
                    const i = try self.in.readIntLittle(u16);

                    const mod = self.interp.modules.get(path).?.value;
                    break :blk Op.Data{ .LookupFromModule = Op.LookupFromModuleData{ .array = mod.export_vars, .index = i }};
                },
                else => {
                    self.errorByte.* = opbyte;
                    return error.BytecodeInvalidOpByte;
                },
            };
            errdefer opdata.destroy(true, true);

            try ops.append(Op{ .lineno = self.lineno, .data = opdata });
        }

        return Code{
            .nlocalvars = nlocals,
            .ops = ops.toOwnedSlice(),
        };
    }

    pub fn readCodePart(self: *BytecodeReader) !Code {
        const code = try self.readBody();
        errdefer code.destroy(true, true);

        const byte = try self.in.readByte();    // TODO: handle eof?
        if (byte != IMPORT_SECTION) {
            self.errorByte.* = byte;
            return error.BytecodeEndsUnexpectedly;
        }

        return code;
    }
};
