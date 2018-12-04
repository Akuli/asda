import argparse
import sys

from . import bytecode_reader, runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'bytecodefile', type=argparse.FileType('rb'),
        help="a file compiled with asdac")
    args = parser.parse_args()

    # there's a bug in argparse
    if args.bytecodefile is sys.stdin:
        args.bytecodefile = sys.stdin.buffer

    with args.bytecodefile as file:
        if file.read(4) != b'asda':
            print(("%s: '%s' is not a compiled asda file"
                   % (sys.argv[0], args.bytecodefile.name)),
                  file=sys.stderr)
            sys.exit(1)

        opcode = bytecode_reader.read_bytecode(file.read)
        runner.run_file(opcode)


if __name__ == '__main__':
    main()
