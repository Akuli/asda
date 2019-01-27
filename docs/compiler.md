# Asdac Internals

This page documents how `asdac` works, including lots of details. It's
mostly useful for people who want to develop the compiler in some way, or who
just want to know how it works. Right now this page also contains a somewhat
detailed description of asda's syntax, although I'm planning on moving it to a
separate page later.

`asdac`, short for "asda compiler", reads source code from a `.asda` file and
then outputs non-human-readable bytecode to a `.asdac` file. Here's a
high-level overview of how it does that:

![](asdac.png)

Each step is explained more below, but details of asda's syntax are
[here](syntax.md).


## Tokens

Tokenizing is the first step after reading the source code. The tokenizer also
keeps track of indentation and creates indent and dedent tokens appropriately.
For example, in this code...

```js
if a:
 if b:
                c()
```

...or in this code...

```js
if a:
    if b:
        c()
```

...there are indent tokens after `if a:` and `if b:`, and two dedent tokens at
the end of the example code (unless more indented code follows).

The tokenizer also checks for indenting related errors using the fact that the
only valid token sequence containing indents or colons is "colon newline
indent". In other words, every `:` must be followed by a newline and an indent,
and every indent must be preceded by `:` and a newline.


## Raw AST

Unlike e.g. CPython, asdac has two kinds of [AST], and this is the first kind.
At this stage, asdac doesn't know yet anything about the types of variables or
where each variable is defined; raw AST just represents what is done. For
example, the raw AST of `let x = y` tells that a new local variable called `x`
is being created, and its initial value will be the value of a variable called
`y`. It does **not** tell what type the `x` variable will be or which scope the
`y` variable comes from.

[AST]: https://en.wikipedia.org/wiki/Abstract_syntax_tree


## Cooked AST

This is called "cooked" because it's more processed than what I ended up
calling "raw AST". Unlike raw AST, cooked AST contains information about types
of expressions and variables, as well as the scopes that variables are looked
up from (this is represented by a "level" so that 0 means the built-in scope, 1
means the asda file's scope, 2 means a function defined at level 1 etc). Most
error messages related to wrong types, variables being already defined and so
on are created when the raw AST is converted to cooked AST.


## Opcode

This is not AST; instead, opcode consists of instructions for the interpreter
that I ended up calling ops. In the interpreter, there's a stack (basically an
array) of things, and these ops tell the interpreter to push and pop things to
and from the stack. Also, instead of ifs and loops, there are ops that tell the
interpreter to move to a different place in the opcode, a lot like goto
statements in some other programming languages. Instead of "goto", it's called
"jump" in this context.

Along with the stack, running asda code also has an array for local variables.
In the opcode, variables are represented by integers that will later become
indexes of this array of local variables.

When a function defined in asda is called, a new stack and a new local variable
array are created, and all the arguments passed to the function call are added
to the beginning of the local variable array.

Most ops push an object to the stack or pop an item off of the stack. For
example, the op for looking up a variable pushes a variable to the stack, and
the op for jumping conditionally pops a variable off of the stack and jumps if
it's `TRUE`.


## Bytecode

This is opcode that will be written to a binary file in a concise but not
human-readable form. The bytecode files always start with the bytes `asda`; you
may find this useful if you want to figure out whether a random file you have
found might be a compiled asda file. The interpreter displays an error if you
tell it to run a file that doesn't start with `asda`.
