import argparse
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


def source2bytecode(infile, compiled_dir, quiet):
    output_path = common.get_compiled_path(compiled_dir, infile.name)

    infile_stat = os.stat(infile.fileno())
    try:
        outfile_stat = os.stat(output_path)
    except FileNotFoundError:
        compiling = True
    else:
        # compile only if source file is newer than compiled file
        compiling = (infile_stat.st_mtime > outfile_stat.st_mtime)

    if not quiet:
        if compiling:
            eprint("Compiling: %s --> %s" % (
                infile.name, os.path.relpath(output_path, '.')))
        else:
            eprint("No need to recompile %s" % infile.name)

    if not compiling:
        return

    source = infile.read()

    # if you change this, make sure that the last step before opening the
    # output file does NOT produce an iterator, so that if something fails, an
    # exception is likely raised before the output file is opened, and the
    # output file gets left untouched if it exists and no invalid output files
    # are created
    raw = raw_ast.parse(infile.name, source)
    cooked = cooked_ast.cook(raw)
    opcode = opcoder.create_opcode(cooked, infile.name, source)
    bytecode = bytecoder.create_bytecode(opcode)

    with common.open_compiled_file_write(compiled_dir, infile.name) as outfile:
        outfile.write(b'asda')
        outfile.write(bytecode)


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
        'infiles', type=argparse.FileType('r', **common.OPEN_KWARGS),
        nargs=argparse.ONE_OR_MORE, help="source code file")
    parser.add_argument(
        # argparse.FileType('wb') would open the file even if compiling fails
        '--compiled-dir', default='asda-compiled',
        help="directory for compiled asda files, default is ./asda-compiled")
    parser.add_argument(
        '-q', '--quiet', action='store_true',
        help="display less output")
    parser.add_argument(
        '--color', choices=['auto', 'always', 'never'], default='auto',
        help="should error messages be displayed with colors?")
    args = parser.parse_args()

    compiled_dir = os.path.abspath(args.compiled_dir)

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

    if sys.stdin in args.infiles:
        parser.error("reading from stdin is not supported")

    for file in args.infiles:
        try:
            with file:
                source2bytecode(file, compiled_dir, args.quiet)
        except common.CompileError as e:
            report_compile_error(e, red_function)
            sys.exit(1)


if __name__ == '__main__':
    main()
