const Builder = @import("std").build.Builder;
const Mode = @import("builtin").Mode;

pub fn build(b: *Builder) void {
    const mode = b.standardReleaseOptions();
    const exe = b.addExecutable("asdar", "main.zig");
    exe.setBuildMode(mode);

    exe.linkSystemLibrary("c");

    if (mode == Mode.Debug) {
        // this is for valgrinding
        //
        // <andrewrk> Akuli, that's https://github.com/ziglang/zig/issues/896. it's
        //            actually a valgrind bug. we have a workaround:
        // <andrewrk> --no-rosegment compromise security to workaround valgrind bug
        exe.setNoRoSegment(true);
    }

    const run_step = b.step("run", "Run the app");
    const run_cmd = b.addCommand(".", b.env_map, [][]const u8{exe.getOutputPath()});
    run_step.dependOn(&run_cmd.step);
    run_cmd.step.dependOn(&exe.step);

    b.default_step.dependOn(&exe.step);
    b.installArtifact(exe);
}
