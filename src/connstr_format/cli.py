import argparse
import sys

from .stream import normalize_stream


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="connstr-format",
        description="Normalize connection strings, one per line.",
    )
    parser.add_argument(
        "input",
        nargs="?",
        default="-",
        help="file to read (one connection string per line); '-' for stdin",
    )
    parser.add_argument(
        "-o",
        "--output",
        default="-",
        help="file to write to; '-' for stdout (default)",
    )
    args = parser.parse_args(argv)

    in_stream = sys.stdin if args.input == "-" else open(args.input, "r", encoding="utf-8")
    out_stream = sys.stdout if args.output == "-" else open(args.output, "w", encoding="utf-8")
    try:
        for line in normalize_stream(in_stream):
            out_stream.write(line + "\n")
    finally:
        if in_stream is not sys.stdin:
            in_stream.close()
        if out_stream is not sys.stdout:
            out_stream.close()


if __name__ == "__main__":
    main()
