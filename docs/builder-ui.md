# Builder UI Walkthrough

If you are happiest filling out forms instead of writing code, the Builder UI is for you. It lives alongside Polymo and gives you a guided, visual way to design a REST API connector and export it as a ready-to-run [Lakeflow Declarative Pipelines](https://docs.databricks.com/aws/en/dlt/) script.

The Builder generates a standalone Python script — it does not produce a config your pipeline loads at read time. The script imports only `requests`, the standard library, and `pyspark`; polymo itself is not a runtime dependency of anything it generates.

## Getting set up
1. Install the Builder extras: `pip install "polymo[builder]"`.
2. Start the local web app:
   ```bash
   polymo builder --host 127.0.0.1 --port 9000
   ```
3. Open the link shown in your terminal. Chrome, Edge, or any Chromium-based browser works best because they support the built-in file saving features.

> **Tip:** The command checks that PySpark 4 is present. If it is missing, the tool tells you how to install it before continuing.

## Landing screen options
When the page loads you will see three tiles:
- **Start from scratch** – clears everything and opens the form with empty fields.
- **Import Connector** – pick a previously saved `*.polymo.json` config file to continue working on it.
- **Start from an example** – try one of the sample connectors bundled with Polymo (GitHub, JSON Placeholder, etc.).

Every option resets old tokens, previews, and temporary values so you never accidentally reuse secrets. Under the tiles you will also see a **Saved connectors** library. The Builder automatically stores every change in your browser, so closing the tab or hopping back to the landing screen never loses your progress. Open an entry to keep editing, or export/delete configs you no longer need.

## A guided form for your API
The left-hand panel has two tabs: **UI Builder** and **Generated Code**. Stay on the UI Builder tab to describe your connector with plain-language fields. Each section can collapse to keep things tidy.

### 1. Connection basics
- **Base URL** – the root of your API, for example `https://api.example.com`. The builder checks that it looks like a valid URL.
- **Stream Path** – the specific endpoint, such as `/v1/orders`. Enter it exactly how you would type it in a browser.
- **Streaming table** – toggle this on if the generated pipeline should read the stream as a Spark Structured Streaming source (`dp.table` backed by `spark.readStream`) instead of a batch read. Streaming requires an explicit schema and offset- or page-based pagination, and is not compatible with incremental state or partition strategies.

### 2. Authentication (optional)
- Choose **None** if the API is public.
- Choose **Bearer Token** if you have a secret token. The value is stored only in your browser session — never saved to disk or written into the generated script.

### 3. Query parameters & headers
- Use the **Add Parameter** button to include filters like `status: active` or `_limit: 100`.
- Add headers the same way (for example `Accept: application/json`).
- You can use curly braces (`{user_id}`) inside the stream path. Matching parameters are filled in automatically.

### 4. Spark reader options
If your data pipeline supplies values at runtime (like `owner: dan1elt0m`), add them here. These options are shared with the preview and are baked into the generated script's constants.

### 5. Pagination & incremental settings
- Choose the pagination strategy that matches your API's behaviour (none, offset, page, cursor, or link header).
- Incremental fields (`mode`, `cursor_param`, `cursor_field`) power incremental syncs in the generated script. The panel also includes runtime inputs for the state file/URL, initial cursor value, and state key override.

### 6. Record selector (for nested responses)
Some APIs wrap data inside other objects. Use this panel to:
- Point to the right part of the response (e.g. `field_path: data → items`).
- Filter records with simple checks like "keep only items where `record.state == 'open'`".
- Ask Polymo to cast values to the chosen schema so dates look like dates instead of plain text.

### 7. Schema tab
Switch to the **Schema** tab if you need to define the columns yourself. Otherwise leave **Infer schema** turned on and Polymo will guess from sample data.

## The Generated Code pane
Switch to the **Generated Code** tab at any time to see the actual Python script your configuration produces. It updates automatically (with a short debounce) every time you change a field on the UI Builder tab — there is no separate "generate" step and nothing to keep in sync by hand.

- The pane is read-only: edit the connector through the form, not the script.
- **Copy** puts the whole script on your clipboard.
- **Download** saves it as a `.py` file named after the stream, ready to drop into a Lakeflow Declarative Pipelines project.
- If the current configuration doesn't validate yet, an error explaining what's missing appears below the pane instead of a script.

## Previewing your connector
The right-hand panel is where you test your work — this runs the same fetch/pagination/record-selection logic as the generated script, so what you see in the preview is what the exported pipeline will produce.

1. Click **Preview**.
2. The backend validates the config and executes the generated fetch logic against the real API.
3. Pick a view:
   - **DataFrame** shows a tidy table you can page through (10–100 rows per page).
   - **Records** shows the same rows in raw JSON.
   - **Raw API** lists every HTTP call, including headers and any error message.
4. Adjust the **Limit** or **Page size** to control how much data is fetched for the preview.
5. Use **Copy Schema** to copy the column definitions to your clipboard if you want to paste them into docs or scripts.

If something goes wrong — wrong URL, missing token, network issue — the error appears in the status pill and the Raw API view so you can fix it quickly.

## Saving your work
Saving in the Builder is about preserving your work-in-progress *configuration*, not the generated script — download the script separately from the Generated Code pane once you're happy with it.

- The Builder continuously caches your progress locally, so you can step away or experiment without fear — just reopen the connector from the library when you return.
- When you are ready to save a config to disk, press **Save config** (or <kbd>Ctrl/Cmd</kbd> + <kbd>S</kbd>). Name the file in the modal; browsers that support folder access let you pick a target directory once, otherwise the file downloads like any other. Saved configs are JSON (`*.polymo.json`) and may be incomplete drafts — they don't need to validate yet, so you can save and resume later.
- Tokens are never written into the saved config; you re-enter them after reopening a connector.
- Use **Import Connector** on the landing screen to load a previously saved `*.polymo.json` file back into the form.

## Helpful touches
- The theme switcher toggles between light, dark, or "follow my computer" modes.
- The **Connectors** button in the header opens the saved connectors library — autosave means you never lose work when switching between configurations.
- The status pill keeps the latest validation, preview, or save result visible so you know what just happened.

That's it — you now have a friendly workspace for turning API connectors into standalone Lakeflow Declarative Pipelines scripts without hand-writing the boilerplate yourself.
