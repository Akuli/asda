# Asda Interpreter

This runs the bytecode files produced by the compiler.

## Compiling

    $ make

If you have multiple CPU cores and you want to compile faster, run e.g.
`make -j2` to compile 2 files at a time in parallel (that uses two CPU
cores at a time). The number after `-j` shouldn't be greater than the
number of CPU cores; that will consume more RAM without making the build
any faster.

## IWYU

I use `include-what-you-use` with this project, and I have discovered a
bug in IWYU. I created an issue about it
[here](https://github.com/include-what-you-use/include-what-you-use/issues/690).
If that isn't fixed yet, you need to compile and use my fork of IWYU
like this:

1. Add LLVM 8 stuff to your `sources.list` from https://apt.llvm.org and
   install the stuff:

        $ sudo nano /etc/apt/sources.list
        $ sudo apt update
        $ sudo apt install llvm-8-dev libclang-8-dev clang-8

    I have no idea what you should do if you don't have apt. Sorry.

2. Clone my IWYU fork and run `cmake`

        $ mkdir ~/akuli-iwyu
        $ cd ~/akuli-iwyu
        $ git clone https://github.com/Akuli/include-what-you-use
        $ mkdir build
        $ cd build
        $ cmake ../include-what-you-use

    IWYU's instructions pass some options to `cmake` in the last step. I
    have no idea what they do, and I don't use them because the command
    works without them too.

    **If you get a CMake error**, look for `llvm-something` in the error
    message. If the `something` part is NOT `8`, then the build is using
    the wrong LLVM version and you need to remove that. For example, I
    got error messages that said `llvm-4.0`, so I ran these commands:

        $ sudo apt remove llvm-4.0
        $ cd ..
        $ rm -r build
        $ mkdir build
        $ cd build

    and then I ran the cmake command again. (Currently this is not
    mentioned in IWYU's instructions. See [this issue that I
    created](https://github.com/include-what-you-use/include-what-you-use/issues/691).)

3. Compile the IWYU

        $ make -j2

    This takes a long time and about a gigabyte of RAM because IWYU is
    written in C++. I don't like C++.

4. Run the IWYU

        $ cd ~/path/to/asda/asdarc
        $ export IWYU=~/akuli-iwyu/build/bin/include-what-you-use
        $ make iwyu

    If you get an error about IWYU not finding `<stdbool.h>` or some
    other include file, try this instead:

        $ export IWYU='~/akuli-iwyu/build/bin/include-what-you-use -I/usr/include/clang/8/include'
        $ make iwyu

    With this, sometimes IWYU suggest `"stdbool.h"` instead of
    `<stdbool.h>` to me, but at least it's better than nothing. Adding
    `#include <stdbool.h>` instead of copy/pasting IWYU's suggestion
    works, too.

Run `make help` for more instructions.
