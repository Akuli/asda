# try,finally

```js
try:
    try_code
finally:
    finally_code
```

asda's `try,finally` is surprisingly difficult to implement. This file
explains how the implementation works.

Some words that I came up with:

- A "finally state" (FS) represents one of the following things:

    - Nothing special happening
    - Returning from a function without a return value
    - Returning from a function with a return value
    - Throwing an error

    The associated error or return value is included in the FS.

    The interpreter has an "FS stack", which is a list of finally
    states. It is not enough to keep track of one FS because
    `try,finally` statements can be nested.

    Applying an FS means popping an FS from the FS stack and returning,
    throwing or just doing nothing as specified in the FS.

    Discarding an FS means popping an FS from the FS stack and doing
    nothing with it.

- An "error handler" (EH) tells the interpreter that if an error occurs,
  then the interpreter should store the error in a variable specified in
  the EH and then jump to somewhere.

    The interpreter also has a stack for EHs, and when an EH is used,
    it's popped from the stack.

    If an error occurs and the EH stack is non-empty, the topmost EH is
    popped. Then the interpreter stores the error object to a local
    variable and jumps to some location as specified in the popped EH.

    Removing an EH means popping an EH from the EH stack and doing
    nothing with it. This is needed to clean up old error handlers that
    must not be used anymore.

Here is a high-level drawing of what the compiler tells the interpreter
to do for `try,finally` blocks. If the characters `EH` appear near an
arrow, then the arrow represents what happens on an error that is being
handled with an EH. Things marked with `(can fail)` may fail if the
system runs out of memory, although that is unlikely to happen because
the allocations done in those places are quite small.

```
   add EH
 (can fail)
     |
     v
run try code --.
     |         |EH
     v         /
  remove EH   /
       \     /
        \   /
         \ /
          |
          v
      create FS
          |
          v
    push the FS to
     the FS stack
      (can fail)
          |
          v
    add another EH
      (can fail)
          |
          v
   run finally code ------.
          |               |EH
          v               v
      remove EH       discard FS
          |               |
          v               v
       apply FS    throw the error
                  that came from the
                     finally code
```

This setup handles all of the following cases:
- No error in `try` code, no error in `finally` code
- No error in `try` code, error in `finally` code
- Error in `try` code, no error in `finally` code
- Error in `try` code, error in `finally` code

In the case where both codes result in an error, the `try` error is
silently discarded. This is not a good thing, and I may fix it later.
From the drawing it is clear that this can be fixed by adding some code
to the `discard FS` place. In these cases, Python 2 discards the `try`
error silently, but Python 3 attaches the `try` error to the `finally`
error as an attribute, and both errors are displayed in error messages.
