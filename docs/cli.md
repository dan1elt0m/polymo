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
polymo builder --host 127.0.0.1 --port 9000 --reload
```

- `--host` – where to listen (stick with `127.0.0.1` unless you know you need something else).
- `--port` – change the port if 9000 is busy.
- `--reload` – optional. Turn it on only when you are editing the Builder source code and want hot reloads.

When the server is running, it prints a URL. Open it in your browser to use the Builder just like described in the [walkthrough](builder-ui.md). Press <kbd>Ctrl+C</kbd> in the terminal to stop it.

Running `polymo` with no sub-command (or an unrecognized one) prints this help text.
