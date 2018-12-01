# Asda

This is my attempt at making a statically typed programming language.


## Hello World!

Create a file called `hello.asda` with this content:

```js
let greeting = "Hello World!"
print(greeting)
```

Here `let greeting = "Hello World!"` creates a variable of type `Str`, because
`"Hello World!"` is a `Str`. Of course, you can also do `print("Hello World!")`
without a variable. The compiler checks the types at compile time, so this code
doesn't compile (but the compiler produces a good error message):

```js
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

This will create a bytecode file to `asda-compiled/hello.asdac`. Run it with
`pyasda`:

```
$ python3 -m pyasda asda-compiled/hello.asdac
Hello World!
```

`pyasda` is a "temporary" interpreter for the compiled asda files. I'm planning
to write an interpreter in C later, but first I want to get the python
interpreter to work like I want it to work.


## FAQ

### Why is the programming language named asda?

I thought about the name of the programming language for a while. My previous
programming language was called Ö (that's not O, that's Ö), and even though
there's an Ö key on the keyboard right next to the Ä key, some people found Ö
difficult to type for some reason. On the other hand, it's very easy to type
asda. I also searched for "asda programming language" and I didn't find
anything relevant.

### Is there any documentation?

Not yet, but there's [an examples directory](examples/).

### Are there any tests?

Not yet.
