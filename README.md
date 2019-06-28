# Asda

This is my attempt at making a statically typed programming language.


## Hello World!

Make sure that you have:

- Python 3.5 or newer with pip
- git

Then you can download the compiler and the interpreter, and install
their dependencies:

```
$ git clone https://github.com/Akuli/asda
$ cd asda
$ python3 -m pip install --user -r requirements.txt
```

If pip can't install the `regex` module, you may need to install a package that
contains more Python stuff. For example, on Debian-based Linux distributions
you need `sudo apt install python3-dev`.

Next, create a file called `hello.asda` with this content:

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

Anyway, run this to compile your `hello.asda`:

```
$ python3 -m asdac hello.asda
Compiling: hello.asda --> asda-compiled/hello.asdac
```

This creates a bytecode file. Run it with `pyasda`:

```
$ python3 -m pyasda asda-compiled/hello.asdac
Hello World!
```

`pyasda` is a "temporary" interpreter for the compiled asda files. I'm planning
to write an interpreter in C later, but first I want to get the python
interpreter to work like I want it to work.

There isn't much [documentation](docs/) yet, but there are many
[code examples](examples/). All code examples should compile and run nicely.


## FAQ

### Can I compile and run with just one command?

Not yet, but you can combine the two commands conveniently with `&&`:

```
$ python3 -m asdac hello.asda && python3 -m pyasda asda-compiled/hello.asdac
```

### Is the documentation outdated?

Yes. Create an issue if you want me to update it.

### Is there an interactive REPL, like Python's `>>>` prompt?

Not yet, and I'm not sure whether there will ever be one. I like how the
compiler and the interpreter are two separate programs that do different things,
but on the other hand, a REPL would be doable and kind of awesome. It's possible
and not even very hard to get Python programs and C programs to work together.

### Why is the programming language named asda?

I thought about the name of the programming language for a while. My previous
programming language was called Ö (that's not O, that's Ö), and even though
there's an Ö key on the keyboard right next to the Ä key, some people found Ö
difficult to type for some reason. On the other hand, it's very easy to type
asda. I also searched for "asda programming language" and I didn't find
anything relevant.

### How does it work?

I'm sorry, I haven't documented it yet :( If you are actually interested
in this, you can ask me to document stuff by creating an issue.


## Developing asda

This command installs everything you need for developing asda:

```
$ python3 -m pip install --user pytest pytest-cov coverage
```

Or if you like virtualenvs:

```
$ python3 -m venv env
$ . env/bin/activate    # i think this works on windows:  Scripts\activate.bat
(env) $ pip install -r requirements.txt
(env) $ pip install pytest pytest-cov coverage
```

Tests are in `asdac-tests/` and `pyasda-tests/`. `asdac-tests/` is for tests
that don't actually run the code, and `pyasda-tests` compile and run stuff.
There are no tests that run anything without invoking the compiler, because that
would mean writing opcode by hand; the compiler is good at generating opcode and
well tested anyway, so it's much easier to use that for testing the interpreter.

The [examples](examples/) are also tested, and the tests will fail if there are
any examples that aren't getting tested. If the example prints something, the
easiest way to get it tested is to add a text file with the output as contents
to `examples/output`. If that isn't possible (for example, the `while` example
prints forever, and can't be tested with an output file), add a test to
`pyasda-tests/test_examples.py`.

You can run all tests like this:

```
$ python3 -m pytest
```

If you also want to see coverage (the tests will run slower), run them like
this instead:

```
$ python3 -m pytest --cov=asdac --cov=pyasda && python3 -m coverage html
```

Then open `htmlcov/index.html` in your favorite browser to view the results.

The `buggy` folder contains asda codes that don't work like they should
work. Try compiling and running them to see the difference.

There are also READMEs in some subdirectories. Read them too.
