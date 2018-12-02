import argparse
import functools
import os
import re
import sys
import textwrap

import colorama

from . import bytecode, common, cooked_ast, raw_ast, tokenizer


def source2bytecode(infile, outfile):
    assert isinstance(infile.name, str)     # can be e.g. '<stdin>'
    tokens = tokenizer.tokenize(infile.name, infile.read())
    raw = raw_ast.parse(tokens)
    cooked = cooked_ast.cook(raw)

    # if any of the steps above fail, raise an exception here and leave the
    # output file untouched
    cooked = list(cooked)

    with open(outfile, 'wb') as file:
        file.write(b'asda')
        file.write(bytecode.create_bytecode(cooked))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'infile', type=argparse.FileType('r', encoding='utf-8'),
        help="source code file")
    parser.add_argument(
        # argparse.FileType('wb') would open the file even if compiling fails
        # before it's time to write to it
        '-o', '--outfile',
        help=("name of the resulting bytecode file, default is a file in an "
              "asda-compiled subdirectory of where the source file is"))
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

        in_path = os.path.abspath(args.infile.name)
        args.outfile = os.path.join(
            os.path.dirname(in_path),
            'asda-compiled',
            os.path.splitext(os.path.basename(in_path))[0] + '.asdac')
        os.makedirs(os.path.dirname(args.outfile), exist_ok=True)

    try:
        with args.infile:
            source2bytecode(args.infile, args.outfile)
    except common.CompileError as e:
        eprint = functools.partial(print, file=sys.stderr)

        if e.location is None:
            eprint("error: %s" % e.message)
        else:
            eprint("error in %s: %s" % (str(e.location), e.message))

            if args.infile is not sys.stdin:
                before, bad_code, after = e.location.get_source()
                if bad_code.isspace():
                    replacement = '\N{lower one quarter block}'
                    bad_code = re.sub(r'[^\S\n]', replacement, bad_code)
                    bad_code = bad_code.replace('\n', replacement * 3 + '\n')

                gonna_print = before + red_start + bad_code + red_end + after
                eprint()
                eprint(textwrap.indent(gonna_print, ' ' * 4))

        sys.exit(1)


if __name__ == '__main__':
    main()
