"""Normalize connection strings from a line-oriented stream.

The intended input is one connection string per line (a config export, a
grep'd log, a migration script) where the file itself can be arbitrarily
large. `normalize_stream` takes any iterable of lines - a file object, a
list, stdin - and yields normalized results one at a time. It never
concatenates or buffers the whole input; memory use stays proportional to a
single line, not to the file size, because iterating a file object pulls
one line at a time from the OS rather than reading it all upfront.
"""

from .core import normalize, normalize_with_issues


def normalize_stream(lines, skip_blank=True, mask_password=False, aliases=None):
    """Yield normalize(line) for each line in `lines`.

    `lines` is consumed lazily, so passing a file object here (rather than
    file.readlines()) is what keeps this streaming. `mask_password` and
    `aliases` are forwarded to `normalize` on every line; see its
    docstring.
    """
    for line in lines:
        line = line.rstrip("\n").rstrip("\r")
        if skip_blank and not line.strip():
            continue
        yield normalize(line, mask_password=mask_password, aliases=aliases)


def validate_stream(lines, skip_blank=True, aliases=None):
    """Yield (line_number, line, issues) for each line with malformed entries.

    Lines that parse cleanly are not yielded at all, so consuming this is
    naturally "show me what's wrong" rather than a line-by-line echo of the
    whole file. `line_number` is 1-based and counts blank lines even when
    `skip_blank` causes them to be skipped, so it lines up with a text
    editor's view of the file. `aliases` is forwarded to
    `normalize_with_issues`; see its docstring.
    """
    for line_number, line in enumerate(lines, start=1):
        line = line.rstrip("\n").rstrip("\r")
        if skip_blank and not line.strip():
            continue
        _, issues = normalize_with_issues(line, aliases=aliases)
        if issues:
            yield line_number, line, issues
