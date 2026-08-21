"""Normalize connection strings from a line-oriented stream.

The intended input is one connection string per line (a config export, a
grep'd log, a migration script) where the file itself can be arbitrarily
large. `normalize_stream` takes any iterable of lines - a file object, a
list, stdin - and yields normalized results one at a time. It never
concatenates or buffers the whole input; memory use stays proportional to a
single line, not to the file size, because iterating a file object pulls
one line at a time from the OS rather than reading it all upfront.
"""

from .core import normalize


def normalize_stream(lines, skip_blank=True):
    """Yield normalize(line) for each line in `lines`.

    `lines` is consumed lazily, so passing a file object here (rather than
    file.readlines()) is what keeps this streaming.
    """
    for line in lines:
        line = line.rstrip("\n").rstrip("\r")
        if skip_blank and not line.strip():
            continue
        yield normalize(line)
