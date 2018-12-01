import argparse

from . import bytecode_reader


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        'bytecodefile', type=argparse.FileType('rb'),
        help="a file compiled with asdac")
    args = parser.parse_args()

    bytecode_reader.read_bytecode(args.bytecodefile.read)


if __name__ == '__main__':
    main()
