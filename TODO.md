- add yields back, were removed in b0e0fbb because they hadn't been
  maintained in a while and would have made the code more complicated
- some kind of C extension api?
- cyclic import, must choose one:
    - disallow? (add error message to compiler)
    - allow (design semantics and implement)
- generic types in nested functions bug
    is this fixed now? it could be
- docs for Str, Int, Bool and friends
- update asdac tests, go for 100% coverage
- update asdar tests, check coverages with printf or find better coverage tool
- array objects
- union types (may be hard to implement):

        func debug_print(Union[Str, Int] obj):
            print(obj.to_debug_string())

    are they even necessary though?

- optimizations: for non-trivial (read: non-shitty) optimizations, probably need to
  add a new compile step, a directed graph of possible code
  paths that could run
- to_debug_string method to all objects
- oopy subclassy stuff:

        func debug_print(Object obj) -> void:
            print(obj.to_debug_string())

- reference objects: (&some_variable).set("Hello")
- defining classes
- some way to refer to the type of a function, e.g.
  `functype[(Str, Int) -> Bool]` (`functype` can be a keyword)
- interfaces kinda like they are done in rust, e.g. if you are writing a
  JSON lib you could do something like

        interface JsonObject for T:
            functype[(T) -> Str] to_json

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
- getters and setters for attributes
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
  `functype[(Int) -> Str]`, then `run_callback(x => x.to_string())`
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
- case-insensitive vs case-sensitive paths

    python has os.path.normcase, which lowercases a string on windows
    and does nothing on posix. I think that's kinda broken because OSX
    is treated as posix here but typically (not always) is installed on
    a case-insensitive file system?

    the biggest problem is when the interpreter needs to check whether a
    compiled file is imported, given its path. how should it do that?
    I'm thinking of statting the paths as they are imported and storing
    the stat results as keys of a hash table

- how should compiler and interpreter treat symlinks?

    I don't know what is best. Currently they treat them "stupidly" so
    that if you e.g. have a compiled asda file a symlink to it, and a
    different compiled file that imports both, the imported code will
    run twice (but in separate namespaces).
