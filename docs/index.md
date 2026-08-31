# Welcome to Polymo

Polymo turns a REST API into a standalone [Lakeflow Declarative
Pipelines](https://docs.databricks.com/aws/en/dlt/) Python script. Point the
Builder UI at an endpoint, describe pagination/auth/schema through a form,
preview real responses, and export a script — polymo itself is not a
dependency of anything it generates. There is no config file to load, no
custom Spark data source to register, and nothing to `import` from `polymo`
at runtime.

## Why people use Polymo
- **No hand-written boilerplate.** Describe your API once through the
  point-and-click Builder instead of writing pagination/retry/auth code by
  hand.
- **See results before you commit.** Preview the real responses,
  record-by-record, so you can fix issues before exporting.
- **The script is yours.** The export is plain Python (`requests` + the
  standard library + `pyspark`) — read it, edit it, check it into your repo,
  run it anywhere `pyspark` runs.
- **Designed for iterating.** The Builder autosaves your work-in-progress
  connectors locally so you can step away and pick up where you left off.

## Before you start
- Install Polymo with the Builder extras: `pip install "polymo[builder]"`.
- Make sure you have access to the API you care about (base URL, token if
  needed, and any sample request parameters).
- Check that PySpark 4 or newer is available — `polymo builder` checks this
  for you and tells you how to install it if it's missing.

## Quick tour

1. **Launch the Builder.** Run `polymo builder --port 9000` and open the
   link it prints.
2. **Describe your API.** Fill in a base URL like
   `https://jsonplaceholder.typicode.com`, pick the endpoint `/posts`, and
   add filters such as `_limit: 20` if you only need a sample.
3. **Preview the data.** Press **Preview** to see a table of records, the
   raw API replies, and any error messages — this runs the same
   fetch/pagination/record-selection logic the exported script will use.
4. **Export it.** Switch to the **Generated Code** tab and download the
   standalone Python script. Optionally save the work-in-progress form as a
   `*.polymo.json` file too, if you want to keep editing it later.

The Builder keeps a local library of every connector you work on. Use the
header's connector picker to hop between drafts, open the library to rename
or export them, and never worry about losing your place. The header also
shows the Polymo version so you always know which build you're on.

Full walkthrough: [Builder UI](builder-ui.md). Field-by-field reference for
every option and what it generates: [Connector options reference](config.md).

## What's inside this project
- `src/polymo/config.py` and `src/polymo/codegen/` hold the parsing and code
  generation logic — the whole public surface is `generate`, `parse_config`,
  `config_to_dict`, `RestSourceConfig`, and `CodegenError`. See the
  [Python API reference](api.md).
- `polymo builder` is a small web app (FastAPI + React) that guides you
  through every step and calls that same generation logic to power its
  Preview and Generated Code tabs.

## Run the Builder in Docker
- Build the dev-friendly image and launch the Builder with hot reload:

```bash
docker compose up --build builder
```

- The service listens on port `8000`; open <http://localhost:8000> once
  Uvicorn reports it is running.
- The image already bundles PySpark and OpenJDK 21.
- Stop with `docker compose down` and restart quickly using the cached image
  via `docker compose up builder`.

## Coming from polymo 0.x?
0.x's YAML runtime (`spark.read.format("polymo")`, `PolymoConfig`,
`polymo smoke`) is gone in 1.0 — polymo is a dev-time generator only now.
See the [migration guide](migration-1.0.md) for what changed, what to pin if
you're not ready to move, and how to rebuild an old connector in the
Builder.

Have fun building connectors!
