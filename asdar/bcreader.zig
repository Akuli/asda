// bytecode reader

const std = @import("std");
const misc = @import("misc.zig");
const Object = @import("object.zig").Object;
const string_object = @import("objects/string.zig");

const StreamType = std.io.InStream(std.os.File.InStream.Error);

const SET_LINENO: u8 = 'L';
const CREATE_FUNCTION: u8 = 'f';
const LOOKUP_VAR: u8 = 'v';
const SET_VAR: u8 = 'V';
const STR_CONSTANT: u8 = '"';
const NON_NEGATIVE_INT_CONSTANT: u8 = '1';
const NEGATIVE_INT_CONSTANT: u8 = '2';
const TRUE_CONSTANT: u8 = 'T';
const FALSE_CONSTANT: u8 = 'F';
const LOOKUP_METHOD: u8 = 'm';
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



pub const Op = struct {
    pub const VarData = struct{ level: u8, index: u16 };
    pub const CallFunctionData = struct{ returning: bool, nargs: u8 };

    pub const Data = union(enum) {
        LookupVar: VarData,
        CallFunction: CallFunctionData,
        Constant: *Object,

        pub fn destroy(self: Op.Data) void {
            switch(self) {
                Op.Data.Constant => |obj| obj.decref(),
                Op.Data.LookupVar, Op.Data.CallFunction => {},
            }
        }
    };

    lineno: u32,
    data: Data,

    pub fn destroy(op: Op) void {
        op.data.destroy();
    }
};

pub const Code = struct {
    nlocalvars: u16,
    ops: std.ArrayList(Op),

    pub fn destroy(self: *const Code) void {
        var it = self.ops.iterator();
        while (it.next()) |op| {
            op.destroy();
        }

        self.ops.deinit();
    }

    pub fn debugDump(self: *const Code) void {
        var it = self.ops.iterator();
        while (it.next()) |op| {
            std.debug.warn("{}  ", op.lineno);
            switch(op.data) {
                Op.Data.LookupVar => |vardata| std.debug.warn("LookupVar: level={}, index={}\n", vardata.level, vardata.index),
                Op.Data.CallFunction => |funcdata| std.debug.warn("CallFunction: returning={}, nargs={}\n", funcdata.returning, funcdata.nargs),
                Op.Data.Constant => |obj| std.debug.warn("Constant: {}, refcount={}\n", &obj, obj.refcount),
            }
        }
    }
};

// invalid op byte error would be quite useless if one doesn't know what the invalid byte is
pub const ReadResult = union(enum) {
    ByteCode: Code,
    InvalidOpByte: u8,
};

const BytecodeReader = struct {
    allocator: *std.mem.Allocator,
    in: *StreamType,
    lineno: u32,

    fn init(allocator: *std.mem.Allocator, in: *StreamType) BytecodeReader {
        return BytecodeReader{ .allocator = allocator, .in = in, .lineno = 1 };
    }

    // return value must be freed with the allocator
    fn readString(self: *BytecodeReader) ![]u8 {
        const len = try self.in.readIntLittle(u32);
        const result = try self.allocator.alloc(u8, len);
        errdefer self.allocator.free(result);

        try self.in.readNoEof(result);
        return result;
    }

    fn readBody(self: *BytecodeReader) !ReadResult {
        const nlocals = try self.in.readIntLittle(u16);
        var ops = std.ArrayList(Op).init(self.allocator);
        errdefer (Code{ .nlocalvars = nlocals, .ops = ops }).destroy();

        while (true) {
            var opbyte = try self.in.readByte();
            if (opbyte == SET_LINENO) {
                self.lineno = try self.in.readIntLittle(u32);
                opbyte = try self.in.readByte();
                if (opbyte == SET_LINENO) {
                    return error.BytecodeRepeatedLineno;
                }
            }

            const opdata: ?Op.Data = switch(opbyte) {
                END_OF_BODY => null,    // TODO: learn to use break correctly instead
                STR_CONSTANT => blk: {
                    const value = try self.readString();
                    defer self.allocator.free(value);
                    const obj = try string_object.newFromUtf8(self.allocator, value);
                    break :blk Op.Data{ .Constant = obj };
                },
                LOOKUP_VAR => blk: {
                    const level = try self.in.readIntLittle(u8);
                    const index = try self.in.readIntLittle(u16);
                    break :blk Op.Data{ .LookupVar = Op.VarData{ .level = level, .index = index }};
                },
                CALL_VOID_FUNCTION, CALL_RETURNING_FUNCTION => blk: {
                    const ret = (opbyte == CALL_RETURNING_FUNCTION);
                    const nargs = try self.in.readIntLittle(u8);
                    break :blk Op.Data{ .CallFunction = Op.CallFunctionData{ .returning = ret, .nargs = nargs }};
                },
                else => {
                    return ReadResult{ .InvalidOpByte = opbyte };
                },
            };

            if (opdata == null) {
                break;
            }
            {
                errdefer opdata.?.destroy();
                try ops.append(Op{ .lineno = self.lineno, .data = opdata.? });
            }
        }

        return ReadResult{ .ByteCode = Code{ .nlocalvars = nlocals, .ops = ops } };
    }
};

// returns whether the stream looks like an asda file
fn readAsdaBytes(stream: *StreamType) !bool {
    var buf = []u8{ 0, 0, 0, 0 };
    if (4 != try stream.read(buf[0..])) {
        return false;
    }
    return std.mem.eql(u8, buf, "asda");
}

pub fn readByteCode(allocator: *std.mem.Allocator, stream: *StreamType) !ReadResult {
    // TODO: don't use a panic for this
    if (!(try readAsdaBytes(stream))) {
        return error.BytecodeNotAnAsdaFile;
    }

    var reader = BytecodeReader.init(allocator, stream);
    const result = try reader.readBody();

    switch(result) {
        ReadResult.InvalidOpByte => {},
        ReadResult.ByteCode => {
            var tmp_buf = []u8{ 0 };
            if (0 != try stream.read(tmp_buf[0..])) {
                return error.BytecodeTrailingGarbage;
            }
        },
    }

    return result;
}
