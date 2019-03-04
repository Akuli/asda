// imports all the files
// useful for testing, this runs all tests:
//
//     $ zig test tester.zig --library c

comptime {
    _ = @import("bcreader.zig");
    _ = @import("builtins.zig");
    _ = @import("interp.zig");
    _ = @import("main.zig");
    _ = @import("misc.zig");
    _ = @import("objtyp.zig");
    _ = @import("objects/index.zig");   // imports all objects
    _ = @import("runner.zig");
}
