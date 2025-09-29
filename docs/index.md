# Welcome to Polymo

Polymo is a helper that turns everyday web APIs into tables you can analyse. Point it at an API, tell it what you want to grab, and Polymo does the heavy lifting of fetching the data and lining it up neatly.

## Why people use Polymo
- **No custom code required.** Describe your API once in a short, friendly YAML file or through the point-and-click Builder.
- **See results before you commit.** Preview the real responses, record-by-record, so you can fix issues early.
- **Works with Spark-based tools.** When you are ready, Polymo serves the data to your analytics stack using the same interface Spark already understands.
- **Designed for teams.** Save reusable connectors, share them across projects, and keep secrets (like tokens) out of files.

## Pick your path
- **Mostly clicking?** Open the [Builder UI](builder-ui.md) and follow the guided screens. It is the easiest way to create a connector from scratch.
- **Prefer a checklist?** Read the [Configuration guide](config.md) for a plain-language tour of every field in the YAML file.
- **Power user?** Jump straight to the [CLI](cli.md) or the [Python helpers](api.md) to automate things.

## Before you start
- Install Polymo with `pip install polymo`. If you want the Builder UI, add the extras: `pip install "polymo[builder]"`.
- Make sure you have access to the API you care about (base URL, token if needed, and any sample request parameters).
- Check that PySpark version 4 or newer is available. Polymo uses Spark under the hood to keep data consistent.

## Quick tour

1. **Launch the Builder (optional but recommended).** Run `polymo builder --port 9000` and open the provided link in your browser.
2. **Describe your API.** Fill in a base URL like `https://jsonplaceholder.typicode.com`, pick the endpoint `/posts`, and add filters such as `_limit: 20` if you only need a sample.
3. **Preview the data.** Press the Preview button to see a table of records, the raw API replies, and any error messages.
4. **Save the connector.** Download the YAML config or write it directly to your project folder. Tokens stay out of the file and are passed in later.
5. **Use it in Spark.** Load the file with the short code snippet below or copy/paste from the Builder’s tips panel.

```python
from pyspark.sql import SparkSession
from polymo import ApiReader

spark = SparkSession.builder.getOrCreate()
spark.dataSource.register(ApiReader)

df = (
    spark.read.format("polymo")
    .option("config_path", "./config.yml")  # YAML you saved from the Builder
    .option("token", "YOUR_TOKEN")  # Only if the API needs one
    # Uncomment the next lines to enable incremental syncs
    # .option("incremental_state_path", "s3://team-bucket/polymo/state.json")
    # .option("incremental_start_value", "2024-01-01T00:00:00Z")
    .load()
)

df.show()
```

### Incremental syncs in one minute
- Add `cursor_param` and `cursor_field` under `incremental:` in your YAML to tell Polymo which API field to track.
- Pass `.option("incremental_state_path", ...)` when reading with Spark. Local paths and remote URLs (S3, GCS, Azure, etc.) work out of the box.
- On the first run, seed a starting value with `.option("incremental_start_value", "...")`. Future runs reuse the stored cursor automatically.
- Override the stored entry name with `.option("incremental_state_key", "...")` if you share a state file across connectors.
- Skip the state path to keep cursors only in memory during the Spark session, or disable that cache with `.option("incremental_memory_state", "false")` if you always want a cold start.

## What’s inside this project
- `src/polymo/` keeps the logic that speaks to APIs and hands data to Spark.
- `polymo builder` is a small web app (FastAPI + React) that guides you through every step.
- `examples/` contains ready-made configs you can copy, tweak, and use for smoke tests.

Whenever you see an unfamiliar term, look for a tooltip or note in the docs—we try to link jargon to plain explanations. Have fun building connectors!
