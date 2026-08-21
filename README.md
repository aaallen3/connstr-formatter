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

Currently handled: semicolon-delimited `key=value` strings (the ODBC /
ADO.NET / OLE DB style used by SQL Server and MySQL's .NET connector).
URL-style strings (`postgres://user:pass@host/db`) aren't supported yet.

## Usage

As a library:

```python
from connstr_format import normalize

normalize("Server=myServer;UID=sa;PWD=hunter2;Database=myDb")
# 'host=myServer;database=myDb;user=sa;password=hunter2'

normalize("data source=myServer; database=myDb; user id=sa; pwd=hunter2")
# 'host=myServer;database=myDb;user=sa;password=hunter2'
```

Note both inputs above normalize to the same output despite different key
spellings, casing, and order.

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
