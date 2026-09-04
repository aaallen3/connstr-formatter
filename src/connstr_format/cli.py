import argparse
import sys

from .stream import normalize_stream, validate_stream


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
    parser.add_argument(
        "--mask-password",
        action="store_true",
        help="replace password values with a fixed placeholder instead of printing them",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="report malformed entries instead of normalizing; exits 1 if any are found",
    )
    args = parser.parse_args(argv)

    in_stream = sys.stdin if args.input == "-" else open(args.input, "r", encoding="utf-8")
    out_stream = sys.stdout if args.output == "-" else open(args.output, "w", encoding="utf-8")
    try:
        if args.validate:
            return _run_validate(in_stream, out_stream)
        for line in normalize_stream(in_stream, mask_password=args.mask_password):
            out_stream.write(line + "\n")
        return 0
    finally:
        if in_stream is not sys.stdin:
            in_stream.close()
        if out_stream is not sys.stdout:
            out_stream.close()


def _run_validate(in_stream, out_stream):
    """Print each malformed entry found in `in_stream`; return the exit status."""
    found_any = False
    for line_number, line, issues in validate_stream(in_stream):
        found_any = True
        out_stream.write(f"line {line_number}: {line}\n")
        for issue in issues:
            out_stream.write(f"  {issue}\n")
    return 1 if found_any else 0


if __name__ == "__main__":
    sys.exit(main())
