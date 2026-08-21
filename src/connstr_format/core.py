"""Normalize semicolon-delimited, key=value connection strings.

This covers the ODBC / ADO.NET / OLE DB style used by SQL Server, MySQL's
.NET connector, and similar drivers, e.g.:

    Server=myServer;UID=sa;PWD=hunter2;Database=myDb

Different tools and driver versions accept different spellings for the same
field ("Server" vs "Data Source" vs "Addr"), inconsistent casing, and
whatever key order the person who wrote the config felt like. This module
maps known aliases to one canonical key and re-emits pairs in a fixed order,
so two connection strings that mean the same thing produce the same output.

URL-style strings (postgres://user:pass@host/db) aren't handled yet.
"""

# Maps a lowercased, known spelling to the canonical field name we emit.
_ALIASES = {
    "server": "host",
    "data source": "host",
    "addr": "host",
    "address": "host",
    "network address": "host",
    "host": "host",
    "port": "port",
    "database": "database",
    "initial catalog": "database",
    "db": "database",
    "uid": "user",
    "user id": "user",
    "username": "user",
    "user": "user",
    "pwd": "password",
    "password": "password",
}

# Known fields are emitted first, in this order; anything else is treated
# as an "extra" field and emitted afterward, sorted by key.
_CANONICAL_ORDER = ("host", "port", "database", "user", "password")


def _split_pairs(raw):
    """Split on ';', but not inside a quoted value.

    A value can be wrapped in matching single or double quotes to contain
    a literal ';' or '=', e.g. Password='a;b=c'.
    """
    pairs = []
    buf = []
    quote = None
    for ch in raw:
        if quote is not None:
            buf.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            continue
        if ch == ";":
            pairs.append("".join(buf))
            buf = []
            continue
        buf.append(ch)
    if buf:
        pairs.append("".join(buf))
    return pairs


def _unquote(value):
    if len(value) >= 2 and value[0] == value[-1] and value[0] in ("'", '"'):
        return value[1:-1]
    return value


def normalize(raw):
    """Return a canonical form of a single connection string.

    Unknown keys are kept (lowercased) rather than dropped, since a field
    this module doesn't recognize might still matter to whoever reads the
    output. Malformed pairs (no '=', or a blank key) are silently skipped,
    matching how most ODBC drivers behave.
    """
    fields = {}
    extras = {}
    for pair in _split_pairs(raw):
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        key, _, value = pair.partition("=")
        key = key.strip().lower()
        if not key:
            continue
        value = _unquote(value.strip())
        canonical_key = _ALIASES.get(key, key)
        if canonical_key in _CANONICAL_ORDER:
            fields[canonical_key] = value
        else:
            extras[canonical_key] = value

    parts = [f"{key}={fields[key]}" for key in _CANONICAL_ORDER if key in fields]
    parts += [f"{key}={extras[key]}" for key in sorted(extras)]
    return ";".join(parts)
