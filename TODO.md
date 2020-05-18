- scala-style `option_array()` method: `null.option_array() = []`, and `a.option_array() = [a]` for any non-null option `a`
- ternary: `` a `f` b `` is same as `f(a, b)`
- add function names to error messages
- `func` instead of `function`? nobody wants to type `function`. similarly `meth` instead of `method`?
- check that all loops work
- pass statements instead of void statements, to make it familiar for python users and avoid reusing same keyword for multiple different things
- keyboard interrupt handling idea: can't `catch` but `finally` works anyhow
- make sure that the incr part of `for init; cond; incr:` gets parsed after body
- get all example files to compile and run
- come up with a nicer alternative for `functype{(A, B) -> C}` syntax
- simpler import syntax

    ```
    import subdirectory/module1.asda
    import subdirectory/blahblah/module2.asda as lel

    print(module1:whatever)
    print(module2:lel)
    ```

    (I have no idea what I've been thinking when I wrote the above example code)

    Honestly I think the following import syntax would be best:

    ```
    import blah from some/path/blah.asda
    ```

    Most of the time you can read this as just `import blah`, but if the imports
    don't work, then you can read the rest of the import to figure out what it's
    trying to do.

- add suport for closure vars

    ```
    function f() -> functype{() -> Int}:
        let i = 0
        return () -> Int:
            i += 1
            return i

    let g = f()
    print("{g()} {g()} {g()}")
    ```

    This should print `1 2 3`, and for that, the `g` function needs
    to hold the `i` value somehow. Can be solved by wrapping `i` into a
    "container" object that the returned function would hold a reference to.

- add yields back, were removed in b0e0fbb because they hadn't been
  maintained in a while and would have made the code more complicated
- finish implementing try,catch,finally
- implicitly put stuff to a `main()` function

- cyclic import, must choose one:
    - disallow? (add error message to compiler)
    - allow (design semantics and implement)
- some kind of C extension api?
- implement generic types, careful with nested functions
- docs for everything
- update asdac tests, go for 100% coverage
- check asdar test coverages with printf or find better coverage tool
- union types:

        union Foo:
            Str a
            Str b
            Int c

        function bar(Foo foo):
            switch foo:
                case a:
                    # foo is a string
                case b:
                    # foo is a string
                case c:
                    # foo is an integer

        bar(123)                # foo.c will be 123
        bar("hello")            # error
        bar(Foo.b("hello"))     # foo.b will be hello

    compiler doesn't know about types, but it must know which member of the union
    is being used. Instead of identifying union members by type, we can identify
    them with their names (or after compiling, integer ID's corresponding to the
    names). This is good because it might be useful to put the same type in the
    union twice.

- oopy subclassy stuff, to_debug_string method to all objects?

        func debug_print(Object obj) -> void:
            print(obj.to_debug_string())

- reference objects: (&some_variable).set("Hello")
- `const` for variables, maybe `let` should const by default to encourage using constness?

    could be difficult to check for corner cases, e.g. what should this do?

    ```
    if FALSE:
        outer const let i = 1
    print(i)
    ```

    maybe just disallow using `outer` and `const` together?
    here's a corner case without `outer`:

    ```
    for void; TRUE; const let wat = "heh":
        print(wat)
    ```

    are there more corner cases left?
    also is this really a good idea? python works fine without constness

- classes and oop:
    - add a way to create class members without taking more arguments in class
    - add some way to run code whenever a new instance is created, maybe a method named `setup()`?
    - `const` for class members (but no `const` for local variables, C has that and I don't use it)
    - `private` for class members and methods
    - `instanceof` or similar
    - idea: add "anti-inheritance", creating class with everything from another
      class except something that we don't want. Would be useful when you want to
      construct an object by filling in only some properties of it and then the
      rest later, such as when asda code gets first parsed and then type checked.
- add syntax for specifying custom getters and setters of attributes
- interfaces kinda like they are done in rust, e.g. if you are writing a
  JSON lib you could do something like

        interface JsonObject for T:
            functype{(T) -> Str} to_json

        implement JsonObject for Int:
            toJson = (Int i) -> Str:
                return i.to_string()

        implement JsonObject for Str:
            toJson = (Str s) -> Str:
                return "\"" + json_escape(s) + "\""

        implement JsonObject for List[JsonObject]:
            toJson = (List[JsonObject] list) -> Str:
                return "[" + list.map(jo => jo.to_json()).join(",") + "]"

    this would not pollute namespace, so `"hello".to_json()` would not
    work, but `cast[JsonObject]("hello").to_json()` or similar would be
    allowed

- pipe syntax, yay or nay? not sure. `"hello"|cast[jsonObject].to_json()`
- specifying base class of generics: `lol[T inherits SomeBaseClass]`
- named function arguments like kwargs in python
- add i/o and stuff enough for rewriting the compiler in asda
- combine compiler and interpreter:

        $ asda examples/hello.asda
        hello world

- automatic types: if `List[T]` was a class, then `List` and
  `List[auto]` would both mean the same thing, detect type from first
  usage of the variable. E.g. if `List[T]`'s constructor takes three
  `T`s as arguments, then each of these lines does the same thing:

        let thing = new List[Str]("a", "b", "c")
        let thing = new List[auto]("a", "b", "c")
        let thing = new List("a", "b", "c")

    easier to implement in a language with reference objects, so should
    wait until compiler is written in asda

- array literals: `["a", "b"]`, type of `[]` could be `Array[auto]` (and automatic
  types should work well enough for this to be actually useful, unlike with mypy)

- design a concept of "common baseclass" or similar, useful for e.g.
  `[x, y]` when `x` and `y` have different types. The interpreter shouldn't know
  much about types, so having an `Object` type or similar makes no sense in asda.
  This means that `[1, "a"]` should be a compile error. If you really want to mix
  strings and integers, you would need to use a Union for that:

    ```
    union Mixed:
        Str s
        Int i

    let foo = [Mixed.i(1), Mixed.s("a")]
    ```

- one-liner lambdas: if `run_callback` wants an argument of type
  `functype{(Int) -> Str}`, then `run_callback(x => x.to_string())`
  should be same as

        run_callback((auto x) -> auto:
            return x.to_string()
        )

    which is then same as

        run_callback((Int x) -> Str:
            return x.to_string()
        )

    Feels weird to use `->` and `=>` for different things?

- relpath and different drives
- how should compiler and interpreter treat symlinks?

    I don't know what is best. Currently they treat them "stupidly" so
    that if you e.g. have a compiled asda file a symlink to it, and a
    different compiled file that imports both, the imported code will
    run twice (but in separate namespaces).
- strings: add a way to iterate through unicode code points forwards and backwards, and convert between unicode code points and (utf-8) strings


## Optimization Ideas

I'm not sure which of these are good ideas. I wrote everything here so
that I won't forget the ideas.

The goal is to make asda at least as fast as python, which it currently
isn't.

- inline functions in compiler
