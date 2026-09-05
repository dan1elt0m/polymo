# Command Line Helpers

Polymo ships a small `polymo` CLI. The bare command launches the local
UI — there are no subcommands.

```bash
polymo --host 127.0.0.1 --port 8000 --reload
```

- `--host` – where to listen (stick with `127.0.0.1` unless you know you need something else).
- `--port` – change the port if 8000 is busy (that's the default).
- `--reload` – optional. Turn it on only when you are editing the UI source code and want hot reloads.

When the server is running, it prints a URL. Open it in your browser to use the UI just like described in the [walkthrough](ui.md). Press <kbd>Ctrl+C</kbd> in the terminal to stop it.

Run `polymo --help` to see the flags:

```
usage: polymo [-h] [--host HOST] [--port PORT] [--reload]
```

`pip install polymo` installs everything the UI needs, including
PySpark. If your install is somehow broken and PySpark can't be imported,
`polymo` prints a reminder to reinstall (`pip install --force-reinstall
polymo`) and exits with status 1 instead of raising an import error.

There are no subcommands: anything after `polymo` that is not one of the
flags above is rejected during argument parsing with a usage error and
exit status 2.
