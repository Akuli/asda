# Asda's Syntax

This page documents asda's syntax. You may find it useful if you want to develop
`asdac` or if you just want to know how the language works in detail.


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

Tab characters are not allowed in the source code, not even in [string tokens].
Personally I like tabs as they are a character just for indentation, but most
other people don't like them, so I disallowed them to make code consistent. If
you want a string that contains a tab, do `"\t"`.


## Identifier Tokens

An identifier token is e.g. `greeting`, `Str` or `uppercase`. It is a wordy and
non-digit character followed by zero or more wordy characters. Note that the
first character can't be a digit, so `2lol` is not a valid identifier, even
though `lol2` is.


## String Tokens

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
- Anything else except `"`, a newline, or `\\`.

The code between `{` and `}` cannot contain any `{` or `}` characters or
anything that a string without `{` and `}` couldn't contain. There must be a
matching `}` after each `{`, and `{}` can't be nested. The code should be an
[indentation] whose value has a [to_string] method that takes no arguments and
returns a string; it will be called to get a part of the resulting string.


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

...is an error because `d()` doesn't match any of the indentations before it;
it's not a part of `if b:` because `c()` is and it's indented less than `d()`,
but it's indented more than `if b:`.

If a line contains nothing but indentation, comments or both, it's treated as a
blank line. For example, this code doesn't compile because there should be
something coming after `if a:`, but there isn't:

```python3
if a:
    # do nothing
else:
    print("a is FALSE")
```

Use a `void` statement instead. It's a [statement](#statements) that does
nothing:

```js
if a:
    void
else:
    print("a is FALSE")
```


## Expressions

An expression is a piece of code that produces a value, like `"Hello"` or `123`.
Expressions may contain other expressions; for example, `"Hello".uppercase()` is
an expression, and the `"Hello"` in it is also an expression. In fact,
`hello.uppercase` is also an expression, so you can do this:

```js
let get_upper_hello = "Hello".uppercase
print(get_upper_hello())
```

Here's a list of all the different kinds of expressions:

- **Integer literal**, like `123`, `-123` or `0`. Integer literals consist of a
  digit 1-9 followed by zero or more 0-9 digits. There can be a `-` in front of
  the digits. As a special case, `0` and `-0` are also valid (but equivalent).
- **String literals** as explained [above](#string-tokens).
- **Variable lookups** that consist of just an [identifier].
- **Generic function lookups** that consist of the name of a [generic] function,
  which is an identifier, and `[ ]` with one or more comma-separated [types] in
  between.
- **Attribute lookups** consist of an expression, `.` and an [identifier].
- **Function calls** consist of an expression, and `( )` with zero or more
  comma-separated expressions in between.


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
  condition must be an [indentation] with type [Bool]. After the
  `if`, there may be zero or more `elif` parts; each `elif` parts has the same
  syntax as the `if` part, but with `elif` instead of `if`. After the `if` and
  the `elif` parts (if there are any), there may be an `else` part, which has
  the same syntax but without a condition expression.

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
  [indentation] with type [Bool].

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


[expression]: #expression
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
