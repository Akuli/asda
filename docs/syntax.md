# Asda's Syntax

This page documents asda's syntax. You may find it useful if you want to develop
`asdac` or if you just want to know how the language works in detail.

In this spec, "comma-separated" means that there are comma [tokens] between the
items (if there are two or more items), but not elsewhere. For example, `a,b,c`
is comma-separated properly, but `,a,b,c` and `a,b,c,` aren't. As special
cases, a single item and no items at all are also considered comma-separated.
In general, "X-separated" means a similar thing with X instead of a comma.


## Source Files

Asda code is always read as UTF-8. If the file starts with an UTF-8 BOM, it's
ignored. Both LF and CRLF line endings are allowed.

Tab characters are not allowed anywhere in the code, not even in [string tokens].
Personally I like tabs as they are a character just for indentation, but most
other people don't like them, so I disallowed them to make code consistent. If
you want a string that contains a tab, do `"\t"`.


## Tokens

A token is a part of code, like a variable name, a `"string"`, an operator like
`(`, or a keyword like `let` or `if`.

If there are spaces at the beginning of a line, that's considered
[indentation], but otherwise whitespace is ignored, so this...

```js
let greeting = "hello world"
print ( greeting )
```

...does the same thing as this...

```js
let greeting="hello world"
print(greeting)
```

...but **not** the same thing as this:

```js
letgreeting=" hello world "
print(greeting)
```

Now `letgreeting` is one token instead of two separate `let` and `greeting`
tokens, and `" hello world "` contains more spaces than `"hello world"`. Those
extra spaces are not ignored because they are not *between* tokens; they are a
part of the [string token].

Some of the different kinds of tokens are documented in more detail below.


### Operator Tokens

Here is a list of the operator tokens. The uses of each token are described in other sections of this spec.

```
== != -> + - * = ` ; : . , [ ] ( )
```

Note that `==` and `= =` are tokenized differently; `==` is one token but `= =` is two tokens.


### Integer Tokens

An integer token is e.g. `123` or `0`.
It consists of a digit 1-9 followed by zero or more 0-9 digits.
As a special case, `0` is also a valid integer literal, even though it doesn't start with a 1-9 digit like all other integer literals do.

Note that `-123` is *not* an integer literal;
it is the `-` [operator] applied to the integer literal `123`.


### Identifier Tokens

In this section, a "letter" means a Unicode character whose category is `Lu`,
`Ll` or `Lo` (uppercase letter, lowercase letter or other letter). Note that
characters from categories `Lm` and `Lt` (modifier letters and titlecase
letters) are not considered "letters" in this section.

An identifier token is e.g. `greeting`, `Str`, `uppercase`. It consists of a
letter or `_` followed by zero or more letters or any one of the characters
`_1234567890`.


### Moduleful Identifier Tokens

These are like two identifier tokens with a `:` token between them, except that
whitespace is not allowed, and the result is one token, not three separate tokens.
For example, `module:symbol` is a moduleful identifier token that looks up an
`export`ed `symbol` from an `import`ed `module` (see [imports]), but `module :symbol` and
`module: symbol` get tokenized as three separate tokens: `module`, `:` and `symbol`.


### String Tokens

In this section, a "special character" means `{`, `}`, `\`, `"` or a newline
character.

A string token begins with `"` and ends with another `"`. Between the quotes,
there can be:

- `\n` to create a newline character.
- `\t` to create a tab character.
- `\"` to create a quote character.
- `\\` to create a backslash character.
- `\{` to create a `{` character.
- `\}` to create a `}` character.
- `{` and `}` with code (an [expression]) in between to run the code and put the result into the string.
- Any non-special character.

The code between `{` and `}` consists of 1 or more non-special characters. The
code should be an [expression] whose value has a [to_string] method that takes
no arguments and returns a string; it will be called to get a part of the
resulting string. In other words, this...

```js
print("{x.y(z)}")
```

...does the same thing as this:

```js
print((x.y(z)).to_string())
```


## Comments

A comment is `#` followed by some text that is ignored by the compiler. If there
is code before the `#` on the same line, the code will be compiled as if the
comment wasn't there. Note that `"#"` is a [string token] that contains the `#`
character, and it has nothing to do with comments.


## Imports

Imports are not [statements] in asda;
imports (zero or more) need to appear in the file *before* all the statements.
The usage is `import "filename" as importname`.

The `importname` is **not** a variable name; it is fine to create a variable with the same name.
This way you don't need to worry about module names when you are creating variables.
For example, the following Python code contains a bug (can you spot it?),
but the equivalent asda code would compile and run and do the right thing:

```python3
import os

if something:
    os = 'windows'
elif something_else:
    os = 'linux'
else:
    ...display error message...

with open(os.path.join('my_files', os, 'file.txt'), 'r') as file:
    ...
```

Use [moduleful identifiers] to access the variables that the imported file has defined with `export let`.

The `"filename"` can be any [string token] that does not contain unescaped
`{` or `}`, and it's treated as a name of an asda source file, relative to the
directory of the file that the `import` statement is in. Always use `/` as the
path separators with `import`; the `/` characters will be replaced with
whatever is appropriate for the operating system, such as `\` on Windows.

If the same module is imported multiple times (possibly from different files),
then the imported file is executed only once,
and every `import` gives access to the same `export`ed things.


## Indentation

The indentation characters must be spaces, but the number of spaces used for
indentation technically doesn't matter. 4 spaces is good style. For
example, this code...

```js
if a:
 if b:
                c()
```

...does the same thing as this code:

```js
if a:
    if b:
        c()
```

However, this...

```js
if a:
    if b:
        c()
      d()
```

...is an error because `d()` doesn't match any of the indentations before it.
On one hand, `d()` seems to be a part of `if b:` because it's indented more than
`if b:`, but on the other hand, `c()` also seems to be a part of `if b:`, even
though `c()` and `d()` are indented differently.

This is valid, of course:

```js
if a:
    if b:
        c()
        d()
```

This is also valid, but does a different thing:

```js
if a:
    if b:
        c()
    d()
```

The indented parts are called **blocks**.
For example, in the above example, `c()` is a block, and so is the following part:

```js
if b:
    c()
d()
```

As you can see, blocks can be nested.

If a line contains nothing but indentation, it's treated as a blank line. For
example, this code doesn't compile because there should be something coming
after `if a:`, but there isn't (because [comments] are ignored):

```python3
if a:
    # do nothing
else:
    print("a is FALSE")
```

Use a `void` statement instead. It's a [statement] that does nothing:

```js
if a:
    void
else:
    print("a is FALSE")
```

Unless mentioned otherwise, variables defined in a block are not visible outside the block.


## Space-Ignoring Mode

Some tokens need to be extracted from the code in **space-ignoring mode**. It
means that all newlines and indentation characters are ignored.

The space-ignoring mode is turned off by default. It gets turned **on**
whenever an opening paren occurs, and the mode before the opening paren is
restored whenever a closing paren occurs. Here "opening paren" means one of
the tokens `(`, `[` and `{`, and you can guess what a "closing paren" is.

The space-ignoring mode is turned **off** whenever the beginning of an indented [block] occurs,
and the mode before the block is restored at the end of the block.

For example, this is valid asda code:

```js
do_something(
        (Int
            x)
                -> Str:
    return x.to_string()
, more,
args, here)
```

Whitespaces between parentheses get ignored here, except for the [block] that
begins at `:` and ends before the first `,`.
The block begins with an indent before `return`; there is an indent,
because the first line has 0 spaces of indentation and the `return` has 4 spaces of indentation.
The block ends at the `,`,
because there is a dedent there (back to 0 spaces of indentation).

Here are more details about how the space-ignoring mode works:

1. `do_something` is parsed without space-ignoring mode.
2. `(` turns on space-ignoring mode, which permits the following newline charater.
3. `(Int x)` turns on the space-ignoring mode, parses `Int x` and then restores
    it to the state set by the first `(`; that is, the space-ignoring mode
    remains turned on.
4. The newline and `-> Str` get parsed with the space-ignoring mode from the
    first `(`.
5. The block is parsed **without** space-ignoring mode.
    It begins with an [indent],
    because the previous non-space-ignoring-mode part was `do_something`,
    and the `return` is indented more than `do_something`.
    It ends with a dedent, because the first `,` is indented by the same level as `do_something`.
    Space-ignoring mode is turned on and immediately off again for the parentheses of `x.to_string()`.
6. Space-ignoring mode is still turned on from the first `(`, and it gets
    turned off by the `)` on the last line.

Of course, the above code example is bad style, and you should write it like this instead:

```js
do_something((Int x) -> Str:
    return x.to_string()
, more, args, here)
```

The indentations and stuff in this better-style code are quite straight-forward to understand,
and IMO this is much better than lacking the ability to define multi-line lambdas (like in Python).


## Types

These are the different kinds of syntax for specifying types:

- Type names that are [identifier] tokens, like `Str`.
- A [generic] type name (an [identifier]) followed by `[`, one or more types and
  another `]`. For example, `SomeType[Str]` or `SomeType[Othertype[Str], Int]`.
- Function types consist of the keyword `functype`
  followed by similar syntax as in function definitions (documented in [expressions without operators or calls])
  between `{` and `}`.
  For example, the type of `print` is `functype{(Str) -> void}`.

Types are not objects in asda, so the above syntaxes are not expressions.


## Expressions

An expression is a piece of code that evaluates to an object, like `"Hello"` or `123`.
Expressions may contain other expressions; for example, `"Hello".uppercase()` is
an expression, and the `"Hello"` in it is also an expression. In fact,
`"Hello".uppercase` is also an expression, so you can do this:

```js
let get_upper_hello = "Hello".uppercase
print(get_upper_hello())
```

To define what an expression is, I'll first define some other terms:

- An **expression without operators or calls**.
- An **expression without operators** is like an
    [expression without operators or calls], but it contains function calls.
- An **expression** contains expressions without operators and the operators,
    such as `+` or `*`.


### Expressions without operators or calls

Here is the list of all valid expressions without operators or calls:

- **Function definitions** consist of `(` and `)` with zero or more
    comma-separated argument specifications between them, followed by `->`, a
    return type and a [block]. The return type can be a [type] or the
    keyword `void`. Each argument specification consists of a type and an
    [identifier].

    In the block, the arguments are local variables. Setting a local
    variable that came from a function argument has no effects outside
    the function, which is how local variables behave in general.
- **Parenthesized expressions** consist of `(`, an expression (it can be any
    expression, not necessarily an [expression without operators or calls]) and `)`.
- **Integer literals** consist of an [integer token].
- **String literals** consist of a [string token].
- **Variable lookups** consist of an [identifier] or a [moduleful identifier].
- **Generic variable lookups** are like variable lookups, but followed by `[ ]` with one
  or more comma-separated [types] in between.
- **If expressions** are like `if A then B else C`, where `if`, `then` and
  `else` are keywords, and `A`, `B` and `C` can be any expressions. It is an
  error if the type of `A` is not `Bool` or `B` and `C` have different types.
  The if expression first evaluates `A`, and then `B` or `C` (not both) depending
  on the value of `A`. The result of the if expression is then the result of
  `B` or `C`.
- **`new` expressions** consist of the keyword `new` followed by a [type],
    and then zero or more comma-separated expressions between `(` and `)`.
- **`this` expressions** can be only used in methods of classes,
    and they work like `this` works in many other programming languages (it's `self` in python).


### Expressions without operators

An expression without operators is like an [expression without operators or calls],
but it may have zero or more pairs of `(` and `)` tokens at the end. Between
each `( )`, there is a comma-separated list of zero or more [expressions].


### Expressions (with operators)

An expression consists of operator tokens from the below table, and [expressions without operators].
The table works so that operators higher on the table are applied first.
For example, `a+b*c` calculates `a + (b*c)`, because `*` is higher on the list than `+`.
It's good style to use whitespace to make the precedence easier to see.
For example, `a + b*c` is good style and `a+b * c` is horribly misleading.

| Operator Tokens   | Name                      | Kind                              | Notes                                     |
| ----------------- | ------------------------- | --------------------------------- | ----------------------------------------- |
| `*`               | multiplication            | binary                            | chaining, no division yet (sorry)         |
| `+`, `-`          | addition, substraction    | `+` binary, `-` binary or unary   | chaining when used as a binary operator   |
| `==`, `!=`        | equality, non-equality    | binary                            | trying to use chaining is compile error   |
| `.`               | attribute lookup          | binary                            | right side must be an [identifier] token  |
| `` ` ``           | infix function call       | ternary                           | chaining                                  |

Note that the backtick `` ` `` and the single quote `'` are different characters.

An unary operator is used by putting it before an [expression without operators], as in `-123`.
A binary operator goes between two [expressions without operators], e.g. `1 + 2`.
A ternary operator goes between *three* [expressions without operators], e.g. ``a ` b ` c``.

Chaining means that if the operator is used between multiple things, as in `a + b + c + d`, it evaluates `((a + b) + c) + d`.

The infix function call operator works so that ``a ` f ` b`` or ``a `f` b`` (better style) is same as the function call `f(a, b)`.
It is intended to be used when it is natural to read the function name between the two arguments.
For example, if you create an `and` function that takes two bools as arguments and does the obvious thing,
it's better to write ``if thing1 `and` thing2:`` than ``if and(thing1, thing2):``.
The infix operator also chains, so ``a `and` b `and` c`` is same as `and(and(a, b), c)`

It is an error to do e.g. `--x`,
because `-` is an unary operator so you need to put an [expression without operators] after it,
which hasn't been done for the first `-`.
On the other hand, `-(-x)` is valid,
because `(-x)` is an [expression without operators or calls],
so it is also an [expression without operators].


## Statements

A statement is usually a line of code, like `print("Hello")`, but not always;
there are also statements that take up more than one line.
To define exactly what a statement is, I do a similar thing as with [expressions]:
first I define what **one-line-ish statements** are, and then I define what a statement is.

### One-line-ish statements

Due to [space-ignoring mode], `print("Hello")` can also be written like this:

```js
print(
    "Hello"
)
```

This is not one line, even though it does exactly what `print("Hello")` does.
For this reason, I call these things one-line-ish statements instead of one-line statements.

Here is the list of one-line-ish statements:
- **Void statements** consist of the keyword `void` and do nothing.
    See the [indentation] section.
    The `void` keyword also has a different use in the context of defining functions;
    defining a function with `-> void` means that the function does not return a value,
    and this has nothing to do with void statements.
- **Return statements** consist of the keyword `return`, sometimes followed by an [expression].
    Return statements are allowed only inside functions.
    If the function is defined with `-> void`, there must be no expression after the `return` keyword,
    and otherwise the expression is required.
- **Let statements** are like `let varname = value`, where `varname` is an
  [identifier] and `value` is an [expression]. This creates a local variable. It
  is an error if a variable with the given name exists already (regardless of
  whether it is a local variable or some other variable, like a built-in
  variable).

    You can also add the `outer` keyword in front of `let`, as in `outer let varname = value`.
    This adds the variable to an outer scope than where the `let` is.
    For example, this code doesn't compile, because the `if` and `else` [blocks] run in different scopes than the `print`:

    ```js
    if something:
        let string = "a"
    else:
        let string = "b"
    print(string)
    ```

    This works, but is ugly:

    ```js
    let string = "dummy"
    if something:
        string = "a"
    else:
        string = "b"
    print(string)
    ```

    This is the nicest way:

    ```js
    if something:
        outer let string = "a"
    else:
        string = "b"
    ```

    Don't put another `let` statement to the `else` block, because you have already created the variable in the `if` block.

    If there is an `export` keyword in front of the `let`, the variable is
    exported so that other asda files can import the exporting asda file and
    use that variable. For example, if you have this in `a.asda`...

    ```js
    export let message = "lol"
    ```

    ...and this in `b.asda`...

    ```js
    import "a.asda" as a
    print(a.message)
    ```

    ...then compiling `b.asda` will also compile `a.asda` automatically, and
    running `b.asda` will print `lol`.

    Between the variable name and the `=`, there may be `[` and `]` with one or
    more [identifiers] between them. This creates a [generic] variable, and the
    identifiers can be used as types in the value after `=`.

    `export` statements can be used only when creating file-level variables.
    Currently it is not possible to `export` a generic variable, but I'm planning on fixing that.
    Also, combining `outer` and `export` is not allowed.

- **Variable assignment statements** are like `varname = value` without a `let`, but
  otherwise similar to let statements without `export` or `outer`. They change the value of a variable. The
  new value has to be of the same type as the value that was given to the
  variable with `let`.

- **Attribute assignment statements** are like `foo.bar = baz`.
    Here the attribute name `bar` must be an [identifier],
    but `foo` and `baz` can be any [expressions].

- **Function calls** are documented in the [expressions without operators] section.
    When a call to a function that returns something (the function definition does not use `-> void`) is used as a statement,
    the return value of the function is ignored.


### Statements (including non-one-line statements)

- **While statements** consist of `while` followed by a condition and a block.
  The condition must be an [expression] with type [Bool]. This does the same
  thing as in most other programming languages.

- **Do,while statements** have syntax like this:

    ```js
    do:
        block
    while condition
    ```

    This does the same thing as this code...

    ```js
    block
    while condition:
        block
    ```

    ...except that you don't need to write the `block` code twice.

- **If statements** consist of `if` followed by a condition and a block. The
  condition must be an [expression] with type [Bool]. After the `if`, there may
  be zero or more `elif` parts; each `elif` part has the same syntax as the
  `if` part, but with `elif` instead of `if`. After the `if` and the `elif`
  parts, there may be an `else` part, which has the same
  syntax but without a condition expression.

    `elif` works so that this...

    ```js
    if cond1:
        block1
    elif cond2:
        block2
    elif cond3:
        block3
    else:
        block4
    ```

    ...does the same thing as this:

    ```js
    if cond1:
        block1
    else:
        if cond2:
            block2
        else:
            if cond3:
                block3
            else:
                block4
    ```

- **For statements** consist of `for init; cond; incr` followed by a block.
  `init` and `incr` must be [one-line-ish statements], and `cond` must be an
  [expression] with type [Bool].

    The for loop first runs `init`. Then it evaluates `cond`. If `cond` is
    [TRUE], it runs the block and `incr`; if `cond` is `FALSE`, it terminates.
    Checking `cond` and running the block is repeated until `cond` is `FALSE`.

    Variables created in any part of the loop (`init`, `cond`, `incr` and the block)
    are visible in all other parts of the loop, too,
    but not outside the loop.

- **Try statements** consist of `try` and a block, followed by zero more catch parts and an optional finally part.
    There must be at least one catch part or a finally part.

    Catch parts consist of the keyword `catch` followed by an exception [type] and a variable name for the exception, and then a [block].
    When the [error] specified by the type occurs, the catch block runs,
    with an error set to a local variable in the block.
    The variable is not accessible anymore after the block.

    The finally part consists of the keyword `finally` followed by a block.
    It works like in most other programming lanuages.

- **Class statements** consist of `class Foo(Bar baz):` followed by zero or more newline-separated `void` keywords or method definitions.
    Here the `void` keyword is like the void statement, documented in [one-line-ish statements];
    it does nothing.
    `Foo` is the name of the class, and it can be any [identifier].

    The `Bar baz` part is like the similar part in function definitions,
    documented in [expressions without operators or calls].
    It defines the arguments of the constructor.
    Each constructor argument is set to an attribute with a similar name when an instance of the class is created.

    Each method definition consists of the keyword `method`, a method name [identifier],
    and the rest is a function definition.


- All [one-line-ish statements] are also statements.


[comments]: #comments
[block]: #indentation
[blocks]: #indentation
[statement]: #statements
[statements]: #statements
[single-line statements]: #single-line-statements
[indentation]: #indentation
[indented]: #indentation
[indent]: #indentation
[identifier]: #identifier-tokens
[identifiers]: #identifier-tokens
[moduleful identifier]: #moduleful-identifier-tokens
[moduleful identifiers]: #moduleful-identifier-tokens
[tokens]: #tokens
[string token]: #string-tokens
[string tokens]: #string-tokens
[integer token]: #integer-tokens
[type]: #types
[types]: #types
[imports]: #imports
[Bool]: undocumented.md
[TRUE]: undocumented.md
[FALSE]: undocumented.md
[to_string]: undocumented.md
[generic]: undocumented.md
[Generator]: undocumented.md
[operator]: #expressions-with-operators
[operators]: #expressions-with-operators
[space-ignoring mode]: #space-ignoring-mode
[one-line-ish statements]: #one-line-ish-statements
[error]: undocumented.md

[expression without operators or calls]: #expressions-without-operators-or-calls
[expressions without operators or calls]: #expressions-without-operators-or-calls
[expression without operators]: #expressions-without-operators
[expressions without operators]: #expressions-without-operators
[expression]: #expressions
[expressions]: #expressions
