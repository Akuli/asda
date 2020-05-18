import argparse
import functools
import pathlib
import re
import sys
import textwrap
import typing

import colorama     # type: ignore

from asdac import (
    common, parser, typer, decision_tree_creator,
    #optimizer,
    opcode_creator, bytecoder)


def source2bytecode(compilation: common.Compilation) -> None:
    """Compiles a file and saves to compilation.compiled_path"""
    compilation.messager(0, 'Compiling to "%s"...' % common.path_string(
        compilation.compiled_path))

    compilation.messager(3, "Reading the source file")
    with compilation.open_source_file() as file:
        source = file.read()

    compilation.messager(3, "Parsing")
    ast_function_list = parser.parse(compilation, source)

    compilation.messager(3, "Checking types")
    ast_function_list = typer.check_and_add_types(
        compilation, ast_function_list)

    compilation.messager(3, "Creating a decision tree")
    function_trees = decision_tree_creator.create_tree(ast_function_list)

    compilation.messager(3, "Optimizing")
    #decision_tree.graphviz(root_node, 'before_optimization')
#    optimizer.optimize(function_trees)
    #decision_tree.graphviz(root_node, 'after_optimization')

    compilation.messager(3, "Creating opcode")
    opcodes = opcode_creator.create_opcode(function_trees)
    for func, opcode in opcodes.items():
        # f-string inside f-string
        print(f'\n\n{f" {func.name} ".center(50, "=")}\n')
        __import__('pprint').pprint(opcode)

    compilation.messager(3, "Creating bytecode")
    bytecode = bytecoder.create_bytecode(compilation, opcodes, source)

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


class CompileManager:

    def __init__(
            self,
            compiled_dir: pathlib.Path,
            messager: common.Messager):
        self.compiled_dir = compiled_dir
        self.messager = messager

        # {compilation.source_path: compilation}
        self.source_path_2_compilation: typing.Dict[
            pathlib.Path, common.Compilation
        ] = {}

    def compile(self, source_path: pathlib.Path) -> None:
        if source_path in self.source_path_2_compilation:
            compilation = self.source_path_2_compilation[source_path]
            assert compilation.done
            compilation.messager(
                2, ('This has been compiled already (to "%s"). Not compiling '
                    'again.' % common.path_string(compilation.compiled_path)))
            return

        compilation = common.Compilation(source_path, self.compiled_dir,
                                         self.messager)

        self.source_path_2_compilation[source_path] = compilation
        source2bytecode(compilation)
        self.something_was_compiled = True


def report_compile_error(
        error: common.CompileError,
        red_function: typing.Callable[[str], str]) -> None:
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


def make_red(string: str) -> str:
    red_begins = typing.cast(str, colorama.Fore.RED)
    red_ends = typing.cast(str, colorama.Fore.RESET)
    return red_begins + string + red_ends


def path_from_user(string: str) -> pathlib.Path:
    return common.resolve_dotdots(pathlib.Path(string).absolute())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'infiles', nargs=argparse.ONE_OR_MORE, help="source code files")
    parser.add_argument(
        # argparse.FileType('wb') would open the file even if compiling fails
        '--compiled-dir', default='asda-compiled',
        help="directory for compiled asda files, default is ./asda-compiled")
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

    compile_manager = CompileManager(compiled_dir, messager)
    try:
        for path in args.infiles:
            compile_manager.compile(path)
    except common.CompileError as e:
        report_compile_error(e, red_function)
        sys.exit(1)

    for compilation in compile_manager.source_path_2_compilation.values():
        assert compilation.done, compilation


if __name__ == '__main__':      # pragma: no cover
    main()
