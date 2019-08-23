- fix function closures
    - changing variables
- fix error handling stufs
- asdac's bytecode reading stuff is broken
- simpler import syntax
- add yields back, were removed in b0e0fbb because they hadn't been
  maintained in a while and would have made the code more complicated
- add a way to forward-declare variables for e.g. functions that call each other?

    alternatively could cook in two steps instead, first signatures and then definitions,
    but it would lead to weird javascripty hoisting stuff.
    For example, if this is allowed

    ```
    let f = () -> void:
        g()

    let g = () -> void:
        ...
    ```

    then how about this?

    ```
    let a = b
    let b = 123
    ```

    or this?

    ```
    print(message)
    let message = "hello"
    ```

- cyclic import, must choose one:
    - disallow? (add error message to compiler)
    - allow (design semantics and implement)
- some kind of C extension api?
- generic types in nested functions bug
    is this fixed now? it could be
- docs for Str, Int, Bool and friends
- update asdac tests, go for 100% coverage
- update asdar tests, check coverages with printf or find better coverage tool
- union types (may be hard to implement):

        func debug_print(Union[Str, Int] obj):
            print(obj.to_debug_string())

    are they even necessary though?

- to_debug_string method to all objects
- oopy subclassy stuff:

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
    - `const` for class members
    - `private` for class members and methods
    - `instanceof` or similar
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
                return "[" + list.map((JsonObject jo) -> Str:
                    return jo.to_json()
                ).join(",") + "]"

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

- array literals: `["a", "b"]`, type of `[]` could be `Array[auto]`

- design a concept of "common baseclass" or similar, useful for e.g.
  `[x, y]` when `x` and `y` have different types. Should never fall back
  to `Object`, e.g. `[1, "a"]` is compile error and not array of
  `Object`. For the object array you could do
  `[cast[Object](1), cast[Object]("a")]` (but why?)

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

    Feels weird to use `->` and `=>` for different things, but I don't
    have better ideas

- relpath and different drives
- how should compiler and interpreter treat symlinks?

    I don't know what is best. Currently they treat them "stupidly" so
    that if you e.g. have a compiled asda file a symlink to it, and a
    different compiled file that imports both, the imported code will
    run twice (but in separate namespaces).


## Optimization Ideas

I'm not sure which of these are good ideas. I wrote everything here so
that I won't forget the ideas.

The goal is to make asda at least as fast as python, which it currently
isn't.

- strings: use utf-8 as internal representation
    - most code inputs and outputs utf-8 anyway so this will mean less conversions
    - add a way to iterate through the code points (when iterators exist)
    - add a way to iterate through the code points backwards
    - add a way to convert a code point to utf-8 (may be more than 1 byte)

- integers: should be possible to create a new integer from anything
  that fits into a long without any allocations, maybe change Object to
  be something like `union { long intval; struct HeapObject *heapobj; }`
  for this? `HeapObject` would be like all objects are now (reference
  counted etc)

- allocate less `Scope` objects by putting local vars to the runner stack
    - may need to add an optimizer to the compiler to make this useful
    - problem: how to ensure that variables defined in closures work?

        ```
        let f = () -> functype{() -> Int}:
            let i = 0
            return () -> Int:
                i += 1
                return i

        let g = f()
        print("{g()} {g()} {g()}")
        ```

        this should print `1 2 3`, and for that, the `g` function needs
        to hold the `i` value somehow (currently with definition scopes
        and parent scopes)

        maybe could be solved by wrapping `i` into a "container" object
        that the returned function would hold a reference to

- create less runners by inlining functions in compiler
- make the runners use the same stack? this seems complicated, could be
  better to just inline
- asdac: new compile step, a directed graph of possible code
  paths that could run
