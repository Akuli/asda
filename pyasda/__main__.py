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

    opcode = bytecode_reader.read_bytecode(args.bytecodefile.read)
    runner.run_file(opcode)


if __name__ == '__main__':
    main()
