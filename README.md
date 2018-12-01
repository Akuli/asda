# Asda

This is my attempt at making a statically typed programming language.


## Hello World!

Create a file called `hello.asda` with this content:

```
let greeting = "Hello World!"
print(greeting)
```

Here `let greeting = "Hello World!"` creates a variable of type `Str`, because
`"Hello World!"` is a `Str`. Of course, you can also do `print("Hello World!")`
without a variable. The compiler checks the types at compile time, so this code
doesn't compile (but the compiler produces a good error message):

```
print(123)
```

Anyway, to compile your `hello.asda`, make sure that you have Python 3 with pip
installed. Then you can download the compiler and install its dependencies...

```
$ git clone https://github.com/Akuli/asda
$ cd asda
$ python3 -m pip install --user -r requirements.txt
```

...and compile the code:

```
$ python3 -m asdac hello.asda
```

This will create a bytecode file to `asda-compiled/hello.asdac`. Unfortunately
I haven't made an interpreter to run those files yet.


## FAQ

### Why is the programming language named asda?

I thought about the name of the programming language for a while. My previous
programming language was called Ö (that's not O, that's Ö), and even though
there's an Ö key on the keyboard (next to the Ä key), some people found that
hard to type for some reason. On the other hand, it's very easy to type asda. I
also searched for "asda programming language" and I didn't find anything
relevant.
