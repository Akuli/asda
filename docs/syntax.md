# Asda's Syntax

This page documents asda's syntax. You may find it useful if you want to develop
`asdac` or if you just want to know how the language works in detail.


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

Some of the different kinds of tokens are documented in more detail below. The
tokens that aren't documented in more detail are mentioned in other parts of
this documentation. For example, `123` is a valid token, because the
[expression] documentation mentions it, and so are e.g. `(` and `-`. Note that
the operators `==`, `!=` and `->` are treated as one token, so `==` and `= =`
are tokenized differently.


### Identifier Tokens

In this section, a "letter" means a Unicode character whose category is `Lu`,
`Ll` or `Lo` (uppercase letter, lowercase letter or other letter). Note that
characters from categories `Lm` and `Lt` (modifier letters and titlecase
letters) are not considered "letters" in this section.

An identifier token is e.g. `greeting`, `Str` or `uppercase`. It consists of a
letter or `_` followed by zero or more letters or any one of the characters
`_1234567890`.


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
- `{` and `}` with asda code in between to run the code and put the result into
  the string.
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


## Indentation

The indentation characters must be spaces, but the number of spaces used for
indentation technically doesn't matter. However, 4 spaces is good style. For
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


## Expressions

In this section, "comma-separated" means that there are commas between the
items (if there are two or more items), but not elsewhere. For example, `a,b,c`
is comma-separated properly, but `,a,b,c` and `a,b,c,` aren't. As special
cases, a single item and no items at all are also considered comma-separated.
In general, "X-separated" means a similar thing with X instead of a comma.

An expression is a piece of code that produces a value, like `"Hello"` or `123`.
Expressions may contain other expressions; for example, `"Hello".uppercase()` is
an expression, and the `"Hello"` in it is also an expression. In fact,
`"Hello".uppercase` is also an expression, so you can do this:

```js
let get_upper_hello = "Hello".uppercase
print(get_upper_hello())
```

Some expressions are called "simple expressions", while other expressions
consists of operators and simple expressions. Here's a list of all the
different kinds of simple expressions:

- **Integer literal**, like `123` or `0`. Integer literals consist of a digit
  1-9 followed by zero or more 0-9 digits. As a special case, `0` is also a
  valid integer literal, even though it doesn't start with a 1-9 digit like all
  other integer literals do. Note that `-123` is *not* an integer literal; it
  is the prefix operator `-` applied to the integer literal `123` (see below).
- **String literals** consist of a [string token].
- **Variable lookups** consist of an [identifier].
- **Generic function lookups** that consist of the name of a [generic] function,
  which is an identifier, and `[ ]` with one or more comma-separated [types] in
  between.
- **Parenthesized expressions** consist of `(`, an expression (it doesn't have
  to be a simple expression) and `)`.

Simple expressions can have zero or more of the following things at the end,
and they are considered a part of the simple expression:

- **Attribute lookups** consist of `.` and an [identifier].
- **Function calls** consist of `( )` with zero or more comma-separated
  expressions in between.

An expression consists of an optional `-` and one or more operator-separated
simple expressions. For example, `-a + b + c` is valid syntax, and so is `-a`,
but `a + -b` isn't because there are two operators between `a` and `b`. Note
that `a + (-b)` is valid, because `(-b)` with the parentheses is a simple
expression. Also, `x == -1` is not valid syntax because that also contains two
operators between `x` and `1`. I think this is dumb and I might change the
syntax to allow this later.

Here is an operator precedence list. It works so that operators higher on the
list are applied first. Operators of the same precedence are applied
left-to-right. For example, `- a + b + c` does `((- a) + b) + c`, and
`a * b + c / d` does `(a * b) + (c / d)`. As a special case, `==` and `!=`
don't work this way; using them like that as in `a == b == c` is a syntax
error.

In the list, "prefix `-`" means `-` so that it's used like `- something`, not
like `something - something`.

1. `*`, `/`
2. `+`, `-`, prefix `-`
3. `==`, `!=`
4. `` `some_function` ``

The `some_function` can be any expression, and ``a `some_function` b`` does the
same thing as `some_function(a, b)`. Repeated backticks work so that
``a`b`c`d`e`` is treated as ``(a `b` c) `d` e``, not as ``a `(b `c` d)` e``.

It's good style to use whitespace to make the precedence easier to see. For
example, `- a*b + c/d` is good, `- a * b + c / d` is bad, and `-a * b+c / d` is
horribly misleading.

Note that the `/` operator doesn't actually work yet. I added it here just so
that I wouldn't forget to add it later. If it's been a while since I wrote
this, it might actually work. Try it and see:

```js
let x = 1 / 2
print(x.to_string())
```


## Statements

A statement is often a line of code, like `print("Hello")`, but not always;
there are also statements that take up more than one line. Here a "body" means
`:`, a newline, and one or more [indented](#indentation) statements.


### Single-line Statements

- **Let statements** are like `let varname = value`, where `varname` is an
  [identifier] and `value` is an [expression]. This creates a local variable. It
  is an error if a variable with the given name exists already (regardless of
  whether it is a local variable or some other variable, like a built-in
  variable).

    Note that if you have some code like this...

    ```js
    if something:
        let x = 123
    ```

    ...the compiler will think that the `x` exist in the rest of the code, even
    if `something` is [FALSE]; in that case, a runtime error occurs if the `x`
    is actually used. This means that this doesn't compile...

    ```js
    if something:
        let x = 123
    else:
        let x = 456
    ```

    ...but this compiles, and works as expected:

    ```js
    if something:
        let x = 123
    else:
        x = 456
    ```

- **Assignment statements** are like `varname = value` without a `let`, but
  otherwise similar to let statements. They change the value of a variable. The
  new value has to be of the same type as the value that was given to the
  variable with `let`.

- **Void statements** consist of the keyword `void`, and they do nothing. See
  the [indentation] section for example usage.

- **Return statements** consist of `return`, or `return value` where `value` is
  an [expression]. Return statements can only be used in a function definition.
  Returning stops running the function.

    If the function's return type is `void`, `return` must be called without the
    value. Otherwise, `return` must be called with a value, and the type of the
    value must match the function's return type.

    If the function does not call `return`, the function returns implicitly if
    its return type is `void`, but a runtime error occurs otherwise.

    If there is a function definition in the body of another function
    definition, the return type of the innermost function is used.

- **Yield statements** consist of `yield` and an expression. They are only valid
  inside bodies of functions that return `Generator[some type]` (see [Generator]
  docs).

    `yield` works so that this...

    ```js
    func generate_hellos() -> Generator[Str]:
        yield "Hello"
        yield "Hello"
        yield "Hello"

    let helloer = generate_hellos()
    print(next[Str](helloer))
    print(next[Str](helloer))
    print(next[Str](helloer))
    ```

    ...prints `"hello"` 3 times.

    If a function contains a `yield` (but if the function contains a definition
    of another function, the yields of the innermost function don't count), it
    must not contain `return` with a value, but it may contain `return` without
    a value; this works as usual. However, a function that returns
    `Generator[some type]` doesn't need to yield; instead of yielding, it can
    also return a generator object just like functions return values in general.
    Like this:

    ```js
    func generate_more_hellos() -> Generator[Str]:
        return generate_hellos()
    ```

    Now `generate_hellos()` and `generate_more_hellos()` work the same way.


### Multiline Statements

- **If statements** consist of `if` followed by a condition and a body. The
  condition must be an [expression] with type [Bool]. After the `if`, there may
  be zero or more `elif` parts; each `elif` parts has the same syntax as the
  `if` part, but with `elif` instead of `if`. After the `if` and the `elif`
  parts (if there are any), there may be an `else` part, which has the same
  syntax but without a condition expression.

    `elif` works so that this...

    ```js
    if cond1:
        body1
    elif cond2:
        body2
    elif cond3:
        body3
    else:
        body4
    ```

    ...does the same thing as this:

    ```js
    if cond1:
        body1
    else:
        if cond2:
            body2
        else:
            if cond3:
                body3
            else:
                body4
    ```

- **For statements** consist of `for init; cond; incr` followed by a body.
  `init` and `incr` must be single-line statements, and `cond` must be an
  [expression] with type [Bool].

    The for loop first runs `init`. Then it evaluates `cond`. If `cond` is
    [TRUE], it runs the body and `incr`; if `cond` is `FALSE`, it terminates.
    Checking `cond` and running the body is repeated until `cond` is `FALSE`.

- **While statements** consist of `while` followed by a condition and a body.
  The condition must be an [expression] with type [Bool]. You can think of
  `while cond` as syntactic sugar for `for void; cond; void`.

- **Function definitions** consist of `func` followed by a function name, and
  `(` and `)` with zero or more comma-separated argument specifications between
  them, then `->` (it's an operator token), then a return [type] or the keyword
  `void`, and then a body. Each argument specification consists of a type and an
  [identifier].

    Between the function name and the `(`, there may be `[` and `]` with one or
    more [identifiers] between them. This creates a [generic] function, and the
    identifiers can be used as types in the argument specifications, the return
    type and in the body.

    In the body, the arguments can be used as if they were local variables. When
    the function is called, the corresponding local variables are created, and
    the body is then ran.


## Types

There are two kinds of types:

- Types that are [identifier] tokens, like `Str`.
- A generic type name (an [identifier]) followed by `[`, one or more types and
  another `]`, like `Generator[Str]` or `Generator[Generator[Str]]`.


[comments]: #comments
[expression]: #expression
[statement]: #statements
[indentation]: #indentation
[identifier]: #identifier-tokens
[identifiers]: #identifier-tokens
[string token]: #string-tokens
[string tokens]: #string-tokens
[type]: #types
[types]: #types
[Bool]: undocumented.md
[TRUE]: undocumented.md
[FALSE]: undocumented.md
[to_string]: undocumented.md
[generic]: undocumented.md
[Generator]: undocumented.md
