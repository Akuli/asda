# Asda

This is my attempt at making a statically typed programming language.


## Hello World!

Make sure that you have:

- git
- C compiler that supports C99
- make
- GMP 2
- Python 3.5 or newer
- All the Python dependencies in [asdac-requirements.txt](asdac-requirements.txt)
- Python's development stuff for some of the Python dependencies

If you have `apt`, you can install everything needed like this:

```
$ sudo apt install git gcc make libgmp-dev python3-pip python3-dev
$ python3 -m pip install --user -r asdac-requirements.txt
```

Then you can download and compile all the things:

```
$ git clone https://github.com/Akuli/asda
$ cd asda
$ make
```

This uses `python3` by default. If your Python executable is named something
else than `python3`, such as `python3.5` for example, then run
`export PYTHON=python3.5` before running `make`.

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

Anyway, compile your `hello.asda` with `asdac`, the asda compiler:

```
$ python3 -m asdac hello.asda
Compiling: hello.asda --> asda-compiled/hello.asdac
```

This creates a bytecode file. Run it with `asdar`, the asda runner:

```
$ asdar/asdar asda-compiled/hello.asdac
Hello World!
```

There isn't much [documentation](docs/) yet, but there are many
[code examples](examples/). At the time of writing this, there is only one
example program that doesn't work.


## FAQ-ish

Nobody has actually asked these questions, but I think someone might ask them
if the answers weren't listed here

### Can I compile and run with just one command?

You can combine the two commands conveniently with `&&`:

```
$ python3 -m asdac hello.asda && asdar/asdar asda-compiled/hello.asdac
```

I'm planning on combining the compiler and the interpreter so that running with
just one command is easy.

### Is the documentation outdated?

Yes. Create an issue if you want me to update it.

### Is there an interactive REPL, like Python's `>>>` prompt?

Not yet. I might add an interpreter later, but there are many things that I
want to get done first.

### Why is the programming language named asda?

I thought about the name of the programming language for a while. My previous
programming language was called Ö (that's not O, that's Ö), and even though
there's an Ö key on the keyboard right next to the Ä key, some people found Ö
difficult to type for some reason. On the other hand, it's very easy to type
asda. I also searched for "asda programming language" and I didn't find
anything relevant.


## Developing asda

See [asdar/README.md](asdar/README.md) if you want to work on asdar.

This command installs everything you need for developing `asdac`:

```
$ python3 -m pip install --user pytest pytest-cov coverage
```

Or if you like virtualenvs:

```
$ python3 -m venv env
$ . env/bin/activate    # i think this works on windows:  Scripts\activate.bat
(env) $ pip install -r asdac-requirements.txt
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

You can run asdac tests like this:

```
$ python3 -m pytest asdac-tests
```

If you also want to see coverage (the tests will run slower), run them like
this instead:

```
$ python3 -m pytest --cov=asdac --cov=pyasda && python3 -m coverage html
```

Then open `htmlcov/index.html` in your favorite browser to view the results.

The `buggy` folder contains asda codes that don't work like they should
work. Try compiling and running them to see the difference.
