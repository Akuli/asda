- cyclic import
- generic types in nested functions bug
    is this fixed now? it could be
- docs for Str, Int, Bool and friends
- runtime errors
- ternary operator: if cond then a else b
- optimizations: maybe someone else can do this?
- array objects
- union types (may be hard to implement):

        func debug_print(Union[Str, Int] obj):
            print(obj.to_debug_string())

- to_debug_string method to all objects
- oopy subclassy stuff:

        func debug_print(Object obj) -> void:
            print(obj.to_debug_string())

- reference objects: (&some_variable).set("Hello")
- defining classes
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
