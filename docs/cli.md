# Command Line Helpers

Polymo ships a small `polymo` CLI with a single sub-command: `builder`, which
launches the local Builder UI.

Run `polymo --help` to see the menu:

```
usage: polymo [-h] {builder} ...
```

## `polymo builder`

Starts the local Builder UI.

```bash
polymo builder --host 127.0.0.1 --port 8000 --reload
```

- `--host` – where to listen (stick with `127.0.0.1` unless you know you need something else).
- `--port` – change the port if 8000 is busy (that's the default).
- `--reload` – optional. Turn it on only when you are editing the Builder source code and want hot reloads.

When the server is running, it prints a URL. Open it in your browser to use the Builder just like described in the [walkthrough](builder-ui.md). Press <kbd>Ctrl+C</kbd> in the terminal to stop it.

`polymo builder` needs the `builder` extra (`pip install 'polymo[builder]'`). Running it from a bare `pip install polymo` prints a friendly reminder to install the extra and exits with status 1, instead of raising an import error.

Running `polymo` with no sub-command prints this help text and exits with status 1 — this works even without the `builder` extra installed. An unrecognized sub-command is rejected during argument parsing with a usage error and exit status 2.
