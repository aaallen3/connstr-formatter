# connstr-formatter

Connection strings collected from real environments are never consistent.
The same SQL Server instance shows up as `Server=`, `Data Source=`, or
`Addr=` depending on which tool wrote the config. Keys get reordered,
casing changes, and `UID`/`User Id`/`Username` all mean the same thing.
That makes these strings annoying to diff, grep, or deduplicate.

This tool parses that mess and re-emits each connection string with known
fields mapped to one canonical name and printed in a fixed order
(`host`, `port`, `database`, `user`, `password`, then anything else
sorted alphabetically). Two connection strings that mean the same thing
come out identical.

Two input styles are handled: semicolon-delimited `key=value` strings (the
ODBC / ADO.NET / OLE DB style used by SQL Server and MySQL's .NET connector)
and URL-style strings (`postgres://user:pass@host/db`, `jdbc:sqlserver://...`).

## Usage

As a library:

```python
from connstr_format import normalize

normalize("Server=myServer;UID=sa;PWD=hunter2;Database=myDb")
# 'host=myServer;database=myDb;user=sa;password=hunter2'

normalize("data source=myServer; database=myDb; user id=sa; pwd=hunter2")
# 'host=myServer;database=myDb;user=sa;password=hunter2'

normalize("postgres://sa:hunter2@myServer:5432/myDb")
# 'host=myServer;port=5432;database=myDb;user=sa;password=hunter2'
```

Note all three inputs above normalize to the same fields despite different
key spellings, casing, order, and even a completely different string format.

URL-style parsing also accepts a `jdbc:` prefix and, since some JDBC drivers
(SQL Server's among them) put connection properties after the host as
`;key=value` pairs instead of a query string, both forms work:

```python
normalize("jdbc:postgresql://myServer:5432/myDb?user=sa&password=hunter2")
normalize("jdbc:sqlserver://myServer:1433;databaseName=myDb;user=sa;password=hunter2")
```

From the command line, reading one connection string per line:

```sh
$ cat connections.txt
Server=db1;UID=sa;PWD=hunter2;Database=orders
data source=db2; user id=app; pwd=hunter2; database=orders

$ connstr-format connections.txt
host=db1;database=orders;user=sa;password=hunter2
host=db2;database=orders;user=app;password=hunter2
```

Or via stdin/stdout, which is how it's meant to be used on large files:

```sh
$ cat connections.txt | connstr-format > normalized.txt
```

## Password masking

Normalized output includes the password in plain text by default, which is
fine for feeding into another tool but not for pasting into a log. Pass
`mask_password=True` (or `--mask-password` on the CLI) to replace it with a
fixed placeholder instead:

```python
normalize("Server=db1;UID=sa;PWD=hunter2;Database=orders", mask_password=True)
# 'host=db1;database=orders;user=sa;password=***'
```

```sh
$ connstr-format --mask-password connections.txt
```

The placeholder is a constant string, not `"*" * len(password)`, so the
masked output doesn't leak the password's length either.

## Validation

Malformed segments (no `=`, or a blank key) are silently dropped by
`normalize`, matching how most ODBC drivers behave. If you'd rather know
about those instead of quietly losing fields, use `normalize_with_issues`,
which returns the normalized string alongside a list describing what it
had to skip:

```python
from connstr_format import normalize_with_issues

normalize_with_issues("Server=db1;notapair;=value;Database=orders")
# ('host=db1;database=orders', ["missing '=': 'notapair'", "blank key: '=value'"])
```

From the command line, `--validate` reports malformed entries line by line
instead of printing normalized output, and exits with status 1 if it found
any:

```sh
$ connstr-format --validate connections.txt
line 3: Server=db1;notapair;Database=orders
  missing '=': 'notapair'
```

## Streaming

`connections.txt` above could be a two-line file or a two-million-line
export from a fleet of app servers - the CLI and the library's
`normalize_stream()` handle both the same way. Input is read and processed
one line at a time; nothing accumulates the whole file in memory. Pass a
file object (not `file.readlines()`) if you're calling `normalize_stream`
directly:

```python
from connstr_format import normalize_stream

with open("connections.txt") as f:
    for line in normalize_stream(f):
        print(line)
```

## Install

No dependencies beyond the Python standard library.

```sh
pip install -e .
```

This installs the `connstr-format` command via the entry point in
`pyproject.toml`.
