import argparse
import functools
import pathlib
import re
import sys
import textwrap

import colorama

from . import (bytecoder, common, cooked_ast, decision_tree, opcoder,
               optimizer, raw_ast)


# TODO: error handling for bytecoder.RecompileFixableError
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
    compilation.messager(0, 'Compiling to "%s"...' % common.path_string(
        compilation.compiled_path))

    compilation.messager(3, "Reading the source file")
    with compilation.open_source_file() as file:
        source = file.read()

    compilation.messager(3, "Parsing")
    raw, imports = raw_ast.parse(compilation, source)
    import_compilation_dict = yield imports
    assert import_compilation_dict.keys() == set(imports)
    compilation.set_imports([
        import_compilation_dict[path] for path in imports])

    # TODO: better message for cooking?
    compilation.messager(3, "Creating typed AST")
    cooked, export_vars, export_types = cooked_ast.cook(
        compilation, raw, import_compilation_dict)
    compilation.set_export_types(export_types)

    compilation.messager(3, "Creating a decision tree")
    root_node = decision_tree.create_tree(cooked)

    compilation.messager(3, "Optimizing")
    decision_tree.graphviz(root_node, 'before_optimization')
    optimizer.optimize(root_node)
    decision_tree.graphviz(root_node, 'after_optimization')

    compilation.messager(3, "Creating opcode")
    opcode = opcoder.create_opcode(compilation, root_node, export_vars, source)

    compilation.messager(3, "Creating bytecode")
    bytecode = bytecoder.create_bytecode(compilation, opcode)

    compilation.messager(3, 'Writing bytecode to "%s"' % common.path_string(
        compilation.compiled_path))
    # if you change this, make sure that the last step before opening the
    # output file does NOT produce an iterator, so that if something fails, an
    # exception is likely raised before the output file is opened, and the
    # output file gets left untouched if it exists and no invalid output files
    # are created
    compilation.compiled_path.parent.mkdir(parents=True, exist_ok=True)
    with compilation.compiled_path.open('wb') as outfile:
        outfile.write(bytecode)

    compilation.set_done()
    yield export_types


class CompileManager:

    def __init__(self, compiled_dir, messager, always_recompile):
        self.compiled_dir = compiled_dir
        self.messager = messager
        self.always_recompile = always_recompile

        # remains False forever if all compiled files are up to date
        self.something_was_compiled = False

        # {compilation.source_path: compilation}
        self.source_path_2_compilation = {}

    # there are 2 kinds of up to datenesses to consider:
    #   * has the source file been modified since the previous compilation?
    #   * have the files that are imported been recompiled, or will they need
    #     to be recompiled since the previous compilation?

    def _compiled_is_up2date_with_source(self, compilation):
        try:
            compiled_mtime = compilation.compiled_path.stat().st_mtime
        except FileNotFoundError:
            compilation.messager(3, (
                "Compiled file not found. Need to recompile."))
            return False

        if compiled_mtime < compilation.source_path.stat().st_mtime:
            compilation.messager(3, (
                "The source file is newer than the compiled file. "
                "Need to recompile."))
            return False

        compilation.messager(3, (
            "The compiled file is newer than the source file."))
        return True

    def _compiled_is_up2date_with_imports(self, compilation,
                                          import_compilations):
        compilation_mtime = compilation.compiled_path.stat().st_mtime
        for import_ in import_compilations:
            if compilation_mtime < import_.compiled_path.stat().st_mtime:
                compilation.messager(3, (
                    '"%s" is older than "%s". Need to recompile.' % (
                        common.path_string(compilation.compiled_path),
                        common.path_string(import_.compiled_path))))
                return False

        compilation.messager(3, (
            'No imported files have been recompiled after compiling "%s".' % (
                common.path_string(compilation.compiled_path))))
        return True

    def _compile_imports(self, compilation, imported_paths):
        for path in imported_paths:
            with compilation.messager.indented(2, (
                    '"%s" is imported. ' "Making sure that it's compiled."
                    % common.path_string(path))):
                self.compile(path)

    def compile(self, source_path):
        if source_path in self.source_path_2_compilation:
            compilation = self.source_path_2_compilation[source_path]
            assert compilation.state == common.CompilationState.DONE
            compilation.messager(
                2, ('This has been compiled already (to "%s"). Not compiling '
                    'again.' % common.path_string(compilation.compiled_path)))
            return

        compilation = common.Compilation(source_path, self.compiled_dir,
                                         self.messager)

        if not self.always_recompile:
            with compilation.messager.indented(
                    2, ('Checking if this needs to be compiled to "%s"...'
                        % common.path_string(compilation.compiled_path))):

                if self._compiled_is_up2date_with_source(compilation):
                    # there is a chance that nothing needs to be compiled
                    # but can't be sure yet
                    imports, export_types = bytecoder.read_imports_and_exports(
                        compilation)
                    self._compile_imports(compilation, imports)
                    import_compilations = [self.source_path_2_compilation[path]
                                           for path in imports]

                    # now we can check
                    if self._compiled_is_up2date_with_imports(
                            compilation, import_compilations):
                        compilation.messager(1, "No need to recompile.")
                        compilation.set_imports(import_compilations)
                        compilation.set_export_types(export_types)
                        compilation.set_done()
                        self.source_path_2_compilation[source_path] = (
                            compilation)
                        return

        self.source_path_2_compilation[source_path] = compilation

        generator = source2bytecode(compilation)
        depends_on = next(generator)
        self._compile_imports(compilation, depends_on)

        generator.send({
            path: self.source_path_2_compilation[path]
            for path in depends_on
        })
        self.something_was_compiled = True


def report_compile_error(error, red_function):
    eprint = functools.partial(print, file=sys.stderr)

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


def path_from_user(string):
    return common.resolve_dotdots(pathlib.Path(string).absolute())


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
    parser.add_argument(
        '--color', choices=['auto', 'always', 'never'], default='auto',
        help="should error messages be displayed with colors?")

    verbosity_group = parser.add_mutually_exclusive_group()
    verbosity_group.add_argument(
        '-q', '--quiet', dest='verbosity', action='store_const',
        const=-1, default=0,
        help="print less messages about what is being done")
    verbosity_group.add_argument(
        '-v', '--verbose', dest='verbosity', action='count',
        help=("print more messages, can be given many times for even more "
              "printing"))

    args = parser.parse_args()

    if '-' in args.infiles:
        parser.error("reading from stdin is not supported")

    messager = common.Messager(args.verbosity)

    compiled_dir = path_from_user(args.compiled_dir)
    args.infiles = list(map(path_from_user, args.infiles))
    for source_path in args.infiles:
        if compiled_dir in source_path.parents:
            # I don't even want to think about the corner cases that allowing
            # this would create
            parser.error("refusing to compile '%s' because it is in '%s'"
                         % (common.path_string(source_path),
                            common.path_string(compiled_dir)))

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

    compile_manager = CompileManager(compiled_dir, messager,
                                     args.always_recompile)
    try:
        for path in args.infiles:
            compile_manager.compile(path)
    except common.CompileError as e:
        report_compile_error(e, red_function)
        sys.exit(1)

    for compilation in compile_manager.source_path_2_compilation.values():
        assert compilation.state == common.CompilationState.DONE, compilation

    if not compile_manager.something_was_compiled:
        messager(0, ("Nothing was compiled because the source files haven't "
                     "changed since the previous compilation."))


if __name__ == '__main__':      # pragma: no cover
    main()
