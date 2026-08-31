# Command Line Helpers

Polymo ships a small `polymo` CLI. The bare command launches the local
Builder UI — there are no subcommands.

```bash
polymo --host 127.0.0.1 --port 8000 --reload
```

- `--host` – where to listen (stick with `127.0.0.1` unless you know you need something else).
- `--port` – change the port if 8000 is busy (that's the default).
- `--reload` – optional. Turn it on only when you are editing the Builder source code and want hot reloads.

When the server is running, it prints a URL. Open it in your browser to use the Builder just like described in the [walkthrough](builder-ui.md). Press <kbd>Ctrl+C</kbd> in the terminal to stop it.

Run `polymo --help` to see the flags:

```
usage: polymo [-h] [--host HOST] [--port PORT] [--reload]
```

`pip install polymo` installs everything the Builder needs, including
PySpark. If your install is somehow broken and PySpark can't be imported,
`polymo` prints a reminder to reinstall (`pip install --force-reinstall
polymo`) and exits with status 1 instead of raising an import error.

There are no subcommands: `polymo builder` is rejected during argument
parsing with a usage error and exit status 2, since `builder` is not a
recognized flag.
