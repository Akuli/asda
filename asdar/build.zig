const Builder = @import("std").build.Builder;
const Mode = @import("builtin").Mode;

pub fn build(b: *Builder) void {
    const mode = b.standardReleaseOptions();
    const exe = b.addExecutable("asdar", "main.zig");
    exe.setBuildMode(mode);

    exe.linkSystemLibrary("c");
    exe.linkSystemLibrary("gmp");

    const run = exe.run();
    run.addArg(b.option([]const u8, "file", "asdac file to run").?);
    b.step("run", "run the shit").dependOn(&run.step);

    b.default_step.dependOn(&exe.step);
    b.installArtifact(exe);
}
