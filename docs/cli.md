# Command Line Helpers

Prefer running a quick command instead of opening the Builder? Polymo ships a small `polymo` CLI with two handy sub-commands.

Run `polymo --help` to see the menu:

```
usage: polymo [-h] {builder,smoke} ...
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

## `polymo smoke`
Runs a tiny Spark job to make sure a connector works end-to-end. It reads the YAML file, talks to the API, and prints a few sample rows. Perfect for a quick gut check before scheduling a pipeline.

```bash
polymo smoke --config ./config.yml --limit 10
```

Key switches:

| Flag | Default | What it does |
|------|---------|--------------|
| `--config` | bundled JSONPlaceholder example | Path to your YAML file. Defaults to the example shipped with Polymo. |
| `--stream` | first stream in the file | For future use. Leave blank unless you add more streams later. |
| `--format` | `polymo` | Name of the Spark reader. Change it only if you registered a custom alias. |
| `--limit` | `5` | How many rows to print with `show()`. |
| `--streaming` | off | Run the smoke test with `spark.readStream` instead of `spark.read`. |
| `--stream-batch-size` | `100` | Rows fetched per micro-batch when `--streaming` is used. |

Behind the scenes the command:
1. Checks the file exists (or uses the bundled example).
2. Creates a Spark session called `polymo-smoke`.
3. Registers the Polymo reader.
4. Loads the data (batch or streaming with `trigger(once=True)`), prints the schema, and shows a handful of rows.

If something fails (missing token, wrong URL, etc.), the error bubbles up right away so you can fix it before deploying.

That’s all there is to the CLI—simple shortcuts to launch the Builder or run a “smoke test” whenever you tweak a connector.
