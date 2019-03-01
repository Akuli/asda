import argparse
import sys

from . import bytecode_reader, runner


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('bytecodefile', help="a file compiled with asdac")
    args = parser.parse_args()

    if args.bytecodefile == '-':
        parser.error("reading from stdin is not supported")

    runner.Interpreter().import_path(args.bytecodefile)


if __name__ == '__main__':
    main()
