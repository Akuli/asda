// usage:
//
//  zig build -Dinclude-dir=/usr/include/x86_64-linux-gnu -Dlib-path=/usr/lib/x86_64-linux-gnu/
//
// replace the paths with wherever gmp is installed

const Builder = @import("std").build.Builder;
const Mode = @import("builtin").Mode;

pub fn build(b: *Builder) void {
    const mode = b.standardReleaseOptions();
    const exe = b.addExecutable("asdar", "main.zig");
    exe.setBuildMode(mode);

    exe.addIncludeDir(b.option([]const u8, "include-dir", "E.g. /usr/include/x86_64-linux-gnu").?);
    exe.addLibPath(b.option([]const u8, "lib-path", "E.g. /usr/include/x86_64-linux-gnu").?);

    exe.linkSystemLibrary("c");
    exe.linkSystemLibrary("gmp");

    b.default_step.dependOn(&exe.step);
    b.installArtifact(exe);
}
