"""Normalize connection strings to a canonical, fixed-order form.

Two families of input are handled:

- ODBC / ADO.NET / OLE DB style, semicolon-delimited key=value pairs, used
  by SQL Server, MySQL's .NET connector, and similar drivers, e.g.:

      Server=myServer;UID=sa;PWD=hunter2;Database=myDb

- URL style, used by most non-Windows drivers and JDBC, e.g.:

      postgres://sa:hunter2@myServer:5432/myDb
      jdbc:sqlserver://myServer:1433;databaseName=myDb;user=sa;password=hunter2

Different tools and driver versions accept different spellings for the same
field ("Server" vs "Data Source" vs "Addr"), inconsistent casing, and
whatever key order the person who wrote the config felt like. This module
maps known aliases to one canonical key and re-emits fields in a fixed
order, so two connection strings that mean the same thing produce the same
output, regardless of which of the two styles above they were written in.
"""

import re
from urllib.parse import parse_qsl, unquote

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
    "databasename": "database",
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

# Fixed placeholder for mask_password=True. Fixed width rather than
# something like "*" * len(password) so the output can't leak the
# password's length to anyone reading the masked log.
_PASSWORD_MASK = "***"

# Matches the scheme of a URL-style connection string, with an optional
# "jdbc:" prefix (jdbc:postgresql://..., jdbc:sqlserver://...).
_URL_SCHEME_RE = re.compile(r"^(?:jdbc:)?[a-zA-Z][a-zA-Z0-9+.-]*://")


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


def _assign(key, value, fields, extras, errors, segment):
    """Route one already-decoded key=value pair into fields or extras.

    `segment` is the original text the pair came from, used only to
    describe a blank key in `errors`.
    """
    key = key.strip().lower()
    if not key:
        errors.append(f"blank key: {segment!r}")
        return
    canonical_key = _ALIASES.get(key, key)
    if canonical_key in _CANONICAL_ORDER:
        fields[canonical_key] = value
    else:
        extras[canonical_key] = value


def _parse_keyvalue_pairs(raw, fields, extras, errors):
    """Parse ';'-delimited key=value pairs into fields/extras in place.

    Unknown keys are kept (lowercased) rather than dropped, since a field
    this module doesn't recognize might still matter to whoever reads the
    output. Malformed pairs (no '=', or a blank key) are skipped and
    described in `errors`, matching how most ODBC drivers behave at parse
    time but without silently losing the detail of what was wrong.
    """
    for pair in _split_pairs(raw):
        pair = pair.strip()
        if not pair:
            continue
        if "=" not in pair:
            errors.append(f"missing '=': {pair!r}")
            continue
        key, _, value = pair.partition("=")
        _assign(key, _unquote(value.strip()), fields, extras, errors, pair)


def _split_host_port(hostinfo):
    """Split 'host:port', a bare host, or a bracketed IPv6 '[::1]:port'."""
    if hostinfo.startswith("["):
        end = hostinfo.find("]")
        if end != -1:
            host = hostinfo[1:end]
            rest = hostinfo[end + 1 :]
            if rest.startswith(":") and rest[1:].isdigit():
                return host, rest[1:]
            return host, None
    if ":" in hostinfo:
        host, _, port = hostinfo.rpartition(":")
        if port.isdigit():
            return host, port
    return hostinfo, None


def _parse_url_style(raw, errors):
    """Parse a 'scheme://[user[:pass]@]host[:port][/db][?query]' string.

    Also accepts an optional leading 'jdbc:' and, after the authority, a
    ';key=value;...' tail instead of a query string, which is how
    SQL Server's JDBC driver formats its connection strings.
    """
    fields = {}
    extras = {}

    stripped = raw[len("jdbc:") :] if raw.lower().startswith("jdbc:") else raw
    rest = stripped[stripped.index("://") + 3 :]

    split_at = len(rest)
    for ch in ("/", "?", ";"):
        idx = rest.find(ch)
        if idx != -1 and idx < split_at:
            split_at = idx
    authority, remainder = rest[:split_at], rest[split_at:]

    userinfo, sep, hostinfo = authority.rpartition("@")
    if not sep:
        hostinfo = authority
    else:
        user, _, password = userinfo.partition(":")
        if user:
            fields["user"] = unquote(user)
        if password:
            fields["password"] = unquote(password)

    host, port = _split_host_port(hostinfo)
    if host:
        fields["host"] = unquote(host)
    if port:
        fields["port"] = port

    if remainder.startswith("/"):
        path_end = len(remainder)
        for ch in ("?", ";"):
            idx = remainder.find(ch)
            if idx != -1 and idx < path_end:
                path_end = idx
        database = remainder[1:path_end]
        if database:
            fields["database"] = unquote(database)
        remainder = remainder[path_end:]

    if remainder.startswith("?"):
        for key, value in parse_qsl(remainder[1:], keep_blank_values=True):
            _assign(key, value, fields, extras, errors, f"{key}={value}")
    elif remainder.startswith(";"):
        _parse_keyvalue_pairs(remainder[1:], fields, extras, errors)

    return fields, extras


def normalize_with_issues(raw, mask_password=False):
    """Like `normalize`, but also return a list describing malformed entries.

    Where `normalize` silently drops a segment it can't parse (no '=', or a
    blank key), this returns a `(normalized, issues)` pair where `issues`
    is a list of human-readable strings, one per dropped segment, empty if
    the input was well-formed. Useful for a validation pass over a file
    that would otherwise just quietly lose fields.
    """
    raw = raw.strip()
    errors = []
    if _URL_SCHEME_RE.match(raw):
        fields, extras = _parse_url_style(raw, errors)
    else:
        fields, extras = {}, {}
        _parse_keyvalue_pairs(raw, fields, extras, errors)

    if mask_password and "password" in fields:
        fields["password"] = _PASSWORD_MASK

    parts = [f"{key}={fields[key]}" for key in _CANONICAL_ORDER if key in fields]
    parts += [f"{key}={extras[key]}" for key in sorted(extras)]
    return ";".join(parts), errors


def normalize(raw, mask_password=False):
    """Return a canonical form of a single connection string.

    Accepts either ODBC-style 'key=value;key=value' strings or URL-style
    'scheme://...' strings (including a 'jdbc:' prefix); see the module
    docstring for examples of each.

    If `mask_password` is true and a password field is present, its value
    is replaced with a fixed placeholder instead of the real value, so the
    output is safe to write to a log.

    Malformed segments (no '=', or a blank key) are dropped silently; use
    `normalize_with_issues` if you need to know about those instead of
    losing them quietly.
    """
    return normalize_with_issues(raw, mask_password=mask_password)[0]
