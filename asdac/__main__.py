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


def source2bytecode(infile, outfile_name, quiet):
    if not quiet:
        # without printable_outfile_name it's possible to get this:
        #    Compiling: <stdin> --> -
        printable_outfile_name = (
            '<stdout>' if outfile_name == '-' else outfile_name)
        eprint("Compiling:", infile.name, "-->", printable_outfile_name)

    # if you change this, make sure that the last step before opening the
    # output file does NOT produce an iterator, so that if something fails, an
    # exception is likely raised before the output file is opened, and the
    # output file gets left untouched if it exists and no invalid output files
    # are created
    raw = raw_ast.parse(infile.name, infile.read())
    cooked = cooked_ast.cook(raw)
    opcode = opcoder.create_opcode(cooked)
    bytecode = bytecoder.create_bytecode(opcode)

    # usually argparse.FileType would handle this, but see below
    if outfile_name == '-':
        outfile = sys.stdout.buffer
    else:
        outfile = open(outfile_name, 'wb')

    with outfile:
        outfile.write(b'asda')
        outfile.write(bytecode)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'infile', type=argparse.FileType('r', **common.OPEN_KWARGS),
        help="source code file")
    parser.add_argument(
        # argparse.FileType('wb') would open the file even if compiling fails
        '-o', '--outfile',
        help=("name of the resulting bytecode file, default is a file in an "
              "asda-compiled subdirectory of where the source file is"))
    parser.add_argument(
        '-q', '--quiet', action='store_true',
        help="display less output")
    parser.add_argument(
        '--color', choices=['auto', 'always', 'never'], default='auto',
        help="should error messages be displayed with colors?")
    args = parser.parse_args()

    color_dict = {
        'always': True,
        'never': False,
        'auto': sys.stderr.isatty(),
    }
    if color_dict[args.color]:
        colorama.init()
        red_start = colorama.Fore.RED
        red_end = colorama.Fore.RESET
    else:
        red_start = red_end = ''

    if args.outfile is None:
        if args.infile is sys.stdin:
            parser.error(
                "the -o option is needed when reading source from stdin")

        args.outfile = os.path.join(
            os.path.dirname(args.infile.name),
            'asda-compiled',
            os.path.splitext(os.path.basename(args.infile.name))[0] + '.asdac')
        os.makedirs(os.path.dirname(args.outfile), exist_ok=True)

    try:
        with args.infile:
            source2bytecode(args.infile, args.outfile, args.quiet)
    except common.CompileError as e:
        if e.location is None:
            eprint("error: %s" % e.message)
        else:
            eprint("error in %s: %s" % (str(e.location), e.message))

            if args.infile is not sys.stdin:
                before, bad_code, after = e.location.get_source()
                if not bad_code:
                    bad_code = ' ' * 4      # to make the location visible

                if bad_code.isspace():
                    replacement = '\N{lower one quarter block}'

                    # this doesn't use .expandtabs() because
                    # 'a\tb'.expandtabs(4) puts 3 spaces between a and b
                    #
                    # bad_code is a part of a \n-separated line and not a full
                    # line, so it wouldn't expand it consistently
                    bad_code = re.sub(r'[^\S\n]', replacement,
                                      bad_code.replace('\t', ' ' * 4))
                    bad_code = bad_code.replace('\n', replacement * 3 + '\n')

                gonna_print = before + red_start + bad_code + red_end + after
                eprint()
                eprint(textwrap.indent(gonna_print, ' ' * 4))

        sys.exit(1)


if __name__ == '__main__':
    main()
