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
        $ cmake ../include-what-you-use -DCMAKE_PREFIX_PATH=/usr/lib/llvm-8

    IWYU's instructions pass some options to `cmake` in the last step. I
    have no idea what they do, and I don't use them because the command
    works without them too.

    **If you get a CMake error**, look for `llvm-something` in the error
    message. If the `something` part is NOT `8`, then the build is using
    the wrong LLVM version, and you need to make sure that the `-D` part
    of the `cmake` command ends with 8. The same command is in IWYU's
    README with 7 instead of 8.

3. Compile the IWYU

        $ make -j2

    This takes a long time and about a gigabyte of RAM because IWYU is
    written in C++. I don't like C++.

4. Run the IWYU

        $ cd ~/path/to/asda/asdar
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


## Reference Counts

The interpreter uses reference counting to figure out when objects are not
needed anymore and can be freed. The object struct has a `refcount` integer,
and its value tells how many things are currently using the object.

Incrementing this number is called increffing, and decrementing is called
decreffing. These are done with `OBJECT_INCREF` and `OBJECT_DECREF` defined in
`src/objtyp.h`. Decreffing may destroy the object (that is, `free()` it, decref
other objects that the object refers to etc).

Most functions that return objects expect you to decref the object when you are
done with using it. This is called "returning a new reference". For example,
`boolobject_c2asda(true)` returns an object that represents the asda `TRUE`
constant, and it returns a new reference, so you are supposed to use it like
this:

```c
#include <stdbool.h>
#include "objtyp.h"
#include "objects/bool.h"

void do_something(void)
{
    BoolObject *asdatrue = boolobj_c2asda(true);
    // do something with asdatrue
    OBJECT_DECREF(asdatrue);
}
```

If you create a function that does not return a new reference, then please
**add a comment** about it.


## Common Bugs

Here is some code:

```c
static StringObject *create_a_string(Interp *interp)
{
    char *buf = malloc(123);
    if (!buf)
        return NULL;

    Object *obj = get_another_object_somehow(interp);
    if (!obj)
        return NULL;

    fill the buf using the obj somehow;
    if (filling failed)
        return NULL;

    return stringobj_new_utf8(interp, buf, strlen(buf));
}
```

Even though this code is short, it contains *many* bugs:

- The code does not set an error to the interpreter when `malloc` fails. It
  should do that so that the interpreter can report the error to the user, or
  the asda programmer can handle the error somehow (not implemented yet at the
  time of writing this). Almost all functions do this.

    ```c
    if (!buf) {
        errobj_set_nomem(interp);
        return NULL;
    }
    ```

    If your function returns `NULL` (or some other error marker value, e.g.
    `false` or `-1`) without setting an error to the `interp`, then please
    **add a comment** about it, and make sure to handle the error setting
    whenever you call the function.

    If you want to test whether you got this right, you can replace
    `malloc(123)` with `NULL` in the code and see what it does.

- `get_another_object_somehow()` likely sets an error to `interp` because it
  takes the `interp` as an argument, but if it fails, the `buf` must be freed:

    ```c
    Object *obj = get_another_object_somehow(interp);
    if (!obj) {
        free(buf);
        return NULL;
    }
    ```

    You can use `valgrind` to find missing `free()`s, but in this case you
    would need to also replace `get_another_object_somehow(interp)` with `NULL`
    to see the bug in action.

- If filling the `buf` failed, `buf` must be freed and `obj` must be decreffed
  (see above for more about decreffing). Also make sure that an error is set to
  the `interp` as explained above.

    ```c
    if (filling failed) {
        OBJECT_DECREF(obj);
        free(buf);
        return NULL;
    }
    ```

    If you decref too much or don't incref enough, `valgrind` will report a
    double free or something similar.

    If you incref too much or don't decref enough, there are a couple things
    that can happen:

    - Nothing noticable happens to compile-time created objects. There's no
      good way to find refcount bugs with them.
    - The interpreter and test runner display a warning if you do this for
      objects created at runtime.

- You also need to free `buf` and decref `obj` if everything succeeds or if
  `stringobj_new_utf8` fails. Both of those cases can be handled at once like
  this:

    ```c
    StringObject *res = stringobj_new_utf8(interp, strlen(buf), buf);
    free(buf);
    OBJECT_DECREF(obj);
    return res;   // may be NULL
    ```

    Returning `res` does not create a refcount bug; it just makes
    `create_a_string()` return a new reference on success, which is good.

The `obj` is not needed for anything after filling `buf` with it, so you can
simplify the code by decreffing `obj` earlier, like this:

```c
fill the buf using the obj somehow;
OBJECT_DECREF(obj);
if (filling failed) {
    free(buf);
    return NULL;
}
```

You can also use `goto` for error handling, but as always, make sure that you
get all corner cases right. (No, `goto` is not evil.)


## Code Style

The coding style is Linux kernel style-ish. The "-ish" stands for two things:
1. I'm not nit-picky; it's ok if you don't follow the style exactly. I will likely accept your
   code as it is without complaining about style. (I don't have many
   contributors yet, but I would like to have more people working on this with me.)
2. Some things are done differently than in the kernel style:

    - Long lines are allowed. There is no limit. Break stuff to multiple lines
      whenever it feels good, but no more than that.
    - You generally shouldn't `typedef` every struct you make, but there are
      some typedefs in this project:
        - `Object`, `IntObject`, `StringObject` etc. These are used a **lot** in
          function declarations. These also have a named struct with the same
          name, because those can be forward-declared (see `interp.h`).
        - `Interp`. Also used a lot in function declarations.
        - Callback functions with long signatures. See `objects/func.h`.
    - There are probably some other things that I forgot to mention here. Again,
      don't be nit-picky when it comes to style.


## Performance Graph

Install dependencies:

    $ sudo apt install valgrind graphviz
    $ python3 -m pip install --user gprof2dot

Check that `gprof2dot` is in your `$PATH`:

    $ which gprof2dot

If you get no output, add ~/.local/bin/ to your `$PATH` and try again.

Next, create `hello.asda` in the `asdar` directory:

    $ cp ../examples/hello.asda .

Create the graph:

    $ make graph.png FILE=hello.asda

Now you can open `graph.png` in an image viewer to see the results.
