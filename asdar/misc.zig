const builtin = @import("builtin");
const std = @import("std");


pub fn errorToString(err: anyerror) []const u8 {
    return switch(err) {
        // std.os.PosixOpenError (somewhat copy/pasted from what strerror(3) returns on my system):
        error.FileTooBig => "File too large",
        error.IsDir => "Is a directory",
        error.SymLinkLoop => "Too many levels of symbolic links",
        error.ProcessFdQuotaExceeded => "Too many open files",
        error.SystemFdQuotaExceeded => "Too many open files in the system",
        error.NoDevice => "No such device",
        error.SystemResources => "Not enough system resources",   // corresponds to several different errnos
        error.NoSpaceLeft => "No space left on device",
        error.NotDir => "Not a directory",
        error.DeviceBusy => "Device or resource busy",

        // std.os.WindowsOpenError:
        // TODO: SharingViolation, PipeBusy
        error.InvalidUtf8 => "File name is not valid UTF-8",
        error.BadPathName => "File name contains a character that Windows doesn't allow",

        // these are in both std.os.PosixOpenError and std.os.WindowsOpenError:
        error.PathAlreadyExists => "File or directory exists",
        error.FileNotFound => "No such file or directory",
        error.AccessDenied => "Access denied",
        error.NameTooLong => "Path name is too long",

        // errors that bcreader.zig uses
        error.BytecodeNotAnAsdaFile => "This does not look like an asda bytecode file",
        error.BytecodeRepeatedLineno => "Repeated line number information in bytecode",
        error.BytecodeBeginsUnexpectedly => "The bytecode file begins unexpectedly",
        error.BytecodeEndsUnexpectedly => "The bytecode file ends unexpectedly",
        error.BytecodeInvalidTypeByte => "The bytecode contains an invalid type byte",
        error.BytecodeInvalidOpByte => "The bytecode contains an invalid op byte",

        else => @errorName(err),
    };
}


fn normcaseWindowsPath(path: []u8) void {
    for (path) |c, i| {
        // TODO: also lowercase non-ascii characters
        path[i] =
            if ('A' <= c and c <= 'Z') c+('a'-'A')
            else if (c == '/') '\\'
            else c;
    }
}
fn normcasePosixPath(path: []u8) void { }
pub const normcasePath = if (builtin.os == builtin.Os.windows) normcaseWindowsPath else normcasePosixPath;

test "normcaseWindowsPath" {
    var path: [16]u8 = "ABCXYZabcxyz/\\:.";
    normcaseWindowsPath(path[0..]);
    std.testing.expectEqualSlices(u8, "abcxyzabcxyz\\\\:.", path);
}
