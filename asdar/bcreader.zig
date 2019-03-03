// bytecode reader

const std = @import("std");
const builtins = @import("builtins.zig");
const objtyp = @import("objtyp.zig");
const Object = objtyp.Object;
const objects = @import("objects/index.zig");

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
const LOOKUP_ATTRIBUTE: u8 = '.';
const IMPORT_MODULE: u8 = 'M';
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

    pub const Data = union(enum) {
        LookupVar: VarData,
        SetVar: VarData,
        CallFunction: CallFunctionData,
        Constant: *Object,
        Negation: void,
        JumpIf: u16,

        pub fn destroy(self: Op.Data) void {
            switch(self) {
                Op.Data.Constant => |obj| obj.decref(),
                else => {},
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
    allocator: *std.mem.Allocator,   // for freeing ops
    ops: []Op,
    nlocalvars: u16,

    pub fn destroy(self: *const Code) void {
        for (self.ops) |op| {
            op.destroy();
        }
        self.allocator.free(self.ops);
    }

    pub fn debugDump(self: *const Code) void {
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

// invalid op byte error would be quite useless if one doesn't know what the invalid byte is
// TODO: also include the offset of the invalid byte?
pub const ReadResult = union(enum) {
    ByteCode: Code,
    InvalidOpByte: u8,
    InvalidTypeByte: u8,
};

const ReadTypeResult = union(enum) {
    Type: ?*objtyp.Type,
    InvalidByte: u8,
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

    fn readType(self: *BytecodeReader, firstByte: ?u8) !ReadTypeResult {
        const magic = firstByte orelse try self.in.readByte();

        switch(magic) {
            TYPE_BUILTIN => {
                const index = try self.in.readIntLittle(u8);
                return ReadTypeResult{ .Type = builtins.type_array[index] };
            },
            else => {
                return ReadTypeResult{ .InvalidByte = magic };
            },
        }
    }

    fn readBody(self: *BytecodeReader) !ReadResult {
        const nlocals = try self.in.readIntLittle(u16);

        var ops = std.ArrayList(Op).init(self.allocator);
        errdefer {
            var it = ops.iterator();
            while (it.next()) |op| {
                op.destroy();
            }
            ops.deinit();
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
                    defer self.allocator.free(value);
                    const obj = try objects.string.newFromUtf8(self.allocator, value);
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
                NEGATION => Op.Data{ .Negation = void{} },      // TODO: is void{} best way?
                JUMP_IF => Op.Data{ .JumpIf = try self.in.readIntLittle(u16) },
                CALL_VOID_FUNCTION, CALL_RETURNING_FUNCTION => blk: {
                    const ret = (opbyte == CALL_RETURNING_FUNCTION);
                    const nargs = try self.in.readIntLittle(u8);
                    break :blk Op.Data{ .CallFunction = Op.CallFunctionData{ .returning = ret, .nargs = nargs }};
                },
                CREATE_FUNCTION => blk: {
                    const typ = switch(try self.readType(CREATE_FUNCTION)) {
                        ReadTypeResult.InvalidByte => |byte| {
                            return ReadResult{ .InvalidTypeByte = byte };
                        },
                        ReadTypeResult.Type => |typ| typ,
                    };
                    std.debug.warn("ASDFPOASFOKPK");
                    //const yields = switch(try self.in.readByte()) {
                    //}
                    return ReadResult{ .InvalidOpByte = 1 };
                },
                else => {
                    return ReadResult{ .InvalidOpByte = opbyte };
                },
            };
            errdefer opdata.destroy();

            try ops.append(Op{ .lineno = self.lineno, .data = opdata });
        }

        return ReadResult{ .ByteCode = Code{
            .allocator = self.allocator,
            .nlocalvars = nlocals,
            .ops = ops.toOwnedSlice(),
        }};
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
    if (!(try readAsdaBytes(stream))) {
        return error.BytecodeNotAnAsdaFile;
    }

    var reader = BytecodeReader.init(allocator, stream);
    const result = try reader.readBody();

    switch(result) {
        ReadResult.InvalidOpByte, ReadResult.InvalidTypeByte => {},
        ReadResult.ByteCode => {
            if ((try stream.readByte()) != IMPORT_SECTION) {
                return error.BytecodeEndsUnexpectedly;
            }
        },
    }

    return result;
}
