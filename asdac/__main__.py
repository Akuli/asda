import argparse
import collections
import contextlib
import os
import re
import sys
import textwrap

import colorama

from . import bytecoder, common, cooked_ast, opcoder, raw_ast


# functools.partial(print, file=sys.stderr) doesn't work because tests
# change sys.stderr
def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)


# TODO: error handling for bytecoder.RecompileFixableError
# TODO: quiet or verbose arguments
def source2bytecode(compilation: common.Compilation):
    """Compiles a file.

    Should be used like this:
    1.  Call this function. It does nothing and returns a generator.
    2.  Call next(the_generator). That returns a list of source file names that
        the file being compiled imports.
    3.  Compile the imported files.
    4.  Call the_generator.send(a dict) where the dict's keys are the paths
        from step 2 and the values are Compilation objects.
    5.  Finally, you're done with using this function :D
    """
    eprint("Compiling: %s --> %s" % (
        os.path.relpath(compilation.source_path, '.'),
        os.path.relpath(compilation.compiled_path, '.')))

    with compilation.open_source_file() as file:
        source = file.read()

    raw, imports = raw_ast.parse(compilation, source)
    import_compilation_dict = yield imports
    compilation.set_imports(list(import_compilation_dict.values()))
    cooked, exports = cooked_ast.cook(compilation, raw,
                                      import_compilation_dict)
    compilation.set_exports(exports)

    opcode = opcoder.create_opcode(compilation, cooked, source)
    bytecode = bytecoder.create_bytecode(compilation, opcode)

    # if you change this, make sure that the last step before opening the
    # output file does NOT produce an iterator, so that if something fails, an
    # exception is likely raised before the output file is opened, and the
    # output file gets left untouched if it exists and no invalid output files
    # are created
    os.makedirs(os.path.dirname(compilation.compiled_path), exist_ok=True)
    with open(compilation.compiled_path, 'wb') as outfile:
        outfile.write(bytecode)

    yield exports


class CompileManager:

    def __init__(self, compiled_dir):
        self.compiled_dir = compiled_dir

        # {compilation.source_path: compilation}
        self.source_path_2_compilation = {}

    def compile(self, source_path):
        if source_path in self.source_path_2_compilation:
            return

        compilation = common.Compilation(source_path, self.compiled_dir)
        self.source_path_2_compilation[source_path] = compilation

        generator = source2bytecode(compilation)
        depends_on = next(generator)
        for imported_path in depends_on:
            self.compile(imported_path)

        generator.send({path: self.source_path_2_compilation[path]
                        for path in depends_on})


def report_compile_error(error, red_function):
    if error.location is None:
        eprint("error: %s" % error.message)
        return

    eprint("error in %s: %s" % (
        error.location.get_line_column_string(), error.message))

    try:
        before, bad_code, after = error.location.get_source()
    except OSError:
        return

    if not bad_code:
        bad_code = ' ' * 4      # to make the location visible

    if bad_code.isspace():
        replacement = '\N{lower one quarter block}'

        # this doesn't use .expandtabs() because 'a\tb'.expandtabs(4) puts 3
        # spaces between a and b
        #
        # bad_code is a part of a \n-separated line and not a full line, so it
        # wouldn't expand it consistently
        bad_code = re.sub(r'[^\S\n]', replacement,
                          bad_code.replace('\t', ' ' * 4))
        bad_code = bad_code.replace('\n', replacement * 3 + '\n')

    gonna_print = before + red_function(bad_code) + after
    eprint()
    eprint(textwrap.indent(gonna_print, ' ' * 4))


def make_red(string):
    return colorama.Fore.RED + string + colorama.Fore.RESET


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'infiles', nargs=argparse.ONE_OR_MORE, help="source code files")
    parser.add_argument(
        # argparse.FileType('wb') would open the file even if compiling fails
        '--compiled-dir', default='asda-compiled',
        help="directory for compiled asda files, default is ./asda-compiled")
    parser.add_argument(
        # TODO: respect this flag
        '--always-recompile', action='store_true', default=False,
        help=("always compile all files, even if they have already been "
              "compiled and the compiled files are newer than the source "
              "files"))
#    parser.add_argument(
#        '-q', '--quiet', action='store_true',
#        help="display less output")
    parser.add_argument(
        '--color', choices=['auto', 'always', 'never'], default='auto',
        help="should error messages be displayed with colors?")
    args = parser.parse_args()

    if '-' in args.infiles:
        parser.error("reading from stdin is not supported")

    compiled_dir = os.path.abspath(args.compiled_dir)
    for source_path in args.infiles:
        # yes, this is the best way to check subpathness in python
        nice_source_path = os.path.normcase(os.path.abspath(source_path))
        nice_compiled_dir = os.path.normcase(compiled_dir)
        if nice_source_path.startswith(nice_compiled_dir + os.sep):
            # I don't even want to think about the corner cases that allowing
            # this would create
            parser.error("refusing to compile '%s' because it is in '%s'"
                         % (source_path, compiled_dir))

    color_dict = {
        'always': True,
        'never': False,
        'auto': sys.stderr.isatty(),
    }
    if color_dict[args.color]:
        colorama.init()
        red_function = make_red
    else:
        red_function = lambda string: string    # noqa

    compile_manager = CompileManager(compiled_dir)
    try:
        for file in args.infiles:
            compile_manager.compile(os.path.abspath(file))
    except common.CompileError as e:
        report_compile_error(e, red_function)
        sys.exit(1)

    for compilation in compile_manager.source_path_2_compilation.values():
        assert compilation.state == common.CompilationState.DONE


if __name__ == '__main__':
    #import time
    #start = time.perf_counter()
    main()
    #end = time.perf_counter()
    #print((end-start)*1000, 'ms')
