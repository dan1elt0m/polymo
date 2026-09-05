# Builder UI Walkthrough

If you are happiest filling out forms instead of writing code, the Builder UI is for you. It lives alongside Polymo and gives you a guided, visual way to design a REST API connector and export it as a ready-to-run [Lakeflow Declarative Pipelines](https://docs.databricks.com/aws/en/dlt/) script.

The Builder generates a standalone Python script — it does not produce a config your pipeline loads at read time. The script imports only `requests`, the standard library, and `pyspark`; polymo itself is not a runtime dependency of anything it generates.

## Getting set up
1. Install Polymo: `pip install polymo` (this includes everything the Builder needs, such as PySpark).
2. Start the local web app:
   ```bash
   polymo --host 127.0.0.1 --port 9000
   ```
3. Open the link shown in your terminal. Chrome, Edge, or any Chromium-based browser works best because they support the built-in file saving features.

> **Tip:** The command checks that PySpark 4 is present. If it is missing, that means your install is broken — the tool tells you how to reinstall before continuing.

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
- **Table name** – optional; becomes the dp table name in the generated script. Leave it blank and the builder derives one from the stream path instead.
- **Stream Path** – the specific endpoint, such as `/v1/orders`. Enter it exactly how you would type it in a browser.
- **Streaming table** – every generated `dp.table` reads through a small PySpark custom Data Source registered inline in the script, since Lakeflow Declarative Pipelines requires one either way. Toggle this on to make it a Spark Structured Streaming source (`spark.readStream`) instead of a batch read (`spark.read`) — the same class shape, just a streaming reader instead of a batch one. Streaming requires an explicit schema and offset- or page-based pagination, and is not compatible with incremental state or partition strategies. A batch table with no explicit schema instead samples the first records at read time to derive one — see the [Schema section](config.md#schema) of the config reference.
- **Response format** – choose **JSON** (default) or **XML**. XML responses are flattened by matching an **XML record path** (an `ElementTree.findall()`-style path, e.g. `.//contact`) and cannot be combined with pagination/record-selector features that dig through a JSON payload (cursor path, next-URL path, total-pages path, or a record selector field path). See the [Connector options reference](config.md#xml-responses) for the flattening rules and gotchas.

### 2. Authentication (optional)
- Choose **None** if the API is public.
- Choose **Bearer Token** if you have a secret token. The value is stored only in your browser session — never saved to disk or written into the generated script.
- Choose **API Key** if the API expects the key in a request header or query parameter. Pick a **Placement** (Header or Query parameter) and a **Name** (e.g. `X-API-Key`); the key value itself is stored only in your browser session, same as Bearer.
- Choose **OAuth 2.0 (Client Credentials)** if the API issues tokens via a client-credentials grant. See the [Connector options reference](config.md#authentication) for the full field list.

### 3. Query parameters & headers
- Use the **Add Parameter** button to include filters like `status: active` or `_limit: 100`.
- Add headers the same way (for example `Accept: application/json`).
- You can use curly braces (`{user_id}`) inside the stream path. Matching parameters are filled in automatically.

### 4. Spark reader options
If your data pipeline supplies values at runtime (like `owner: dan1elt0m`), add them here. These options are shared with the preview and are baked into the generated script's constants.

### 5. Pagination & incremental settings
- Choose the pagination strategy that matches your API's behaviour (none, offset, page, cursor, or link header).
- **Incremental sync** – set **Cursor parameter** and **Cursor field** to make the generated script send the last-seen cursor on every request and store the highest value it fetched (**Mode** is a free-text label kept alongside it). **State file or URL** is where the cursor lives between runs (a local path such as a Databricks Volume, or an fsspec URL like `s3://`; default `<stream>_state.json` next to the script), **Initial cursor value** seeds the very first run, and **State key override** names the entry inside a shared state file. All of these end up as constants in the generated script — see [Incremental sync](config.md#incremental-sync).
- **Partitioning** – `Mirror pagination` fans a page/offset-paginated stream out to one Spark partition per page when a total-pages or total-records hint is set; `Parameter range` and `Endpoint list` produce one partition per value or endpoint — see [Partitioning](config.md#partitioning).

### 6. Record selector (for nested responses)
Some APIs wrap data inside other objects. Use this panel to:
- Point to the right part of the response (e.g. `field_path: data → items`).
- Filter records with simple checks like "keep only items where `record.state == 'open'`".
- Ask Polymo to cast values to the chosen schema so dates look like dates instead of plain text.

### 7. Schema tab
Switch to the **Schema** tab if you need to define the columns yourself. Otherwise leave **Infer schema** turned on and Polymo will guess from sample data.

### 8. Filter pushdown
Map DataFrame columns to API query parameters (`status → status`, `owner_id → owner`). Equality filters on those columns are sent to the API as query parameters instead of being applied after the read (Spark 4.1+): `df.filter(col("status") == "active")` becomes `?status=active`. Anything else — other operators, other columns — still works, Spark just evaluates it after the fetch. A pushed value overrides a query parameter of the same name; streaming tables don't support it. The Generated Code pane shows the `pushFilters()` method the mapping produces; the Preview panel is unaffected (it never has filters to push). See [Filter pushdown](config.md#filter-pushdown).

## The Generated Code pane
Switch to the **Generated Code** tab at any time to see the actual Python script your configuration produces. It updates automatically (with a short debounce) every time you change a field on the UI Builder tab — there is no separate "generate" step and nothing to keep in sync by hand.

- The pane is read-only: edit the connector through the form, not the script.
- **Copy** puts the whole script on your clipboard.
- **Download** saves it as a `.py` file named after the stream, ready to drop into a Lakeflow Declarative Pipelines project.
- If the current configuration doesn't validate yet, an error explaining what's missing appears below the pane instead of a script.

## Deploy to Databricks

The **Deploy** tab (next to UI Builder and Generated Code) turns your connector into a full [Databricks Asset Bundle](https://docs.databricks.com/dev-tools/bundles/index.html) project and drives `databricks bundle deploy`/`run` for you, without leaving the Builder.

**Trust model:** the Builder is a localhost, single-user tool. Everything on this tab works by shelling out to the `databricks` CLI already installed on your machine, using whichever profile/auth you picked — the Builder itself never talks to the Databricks REST API directly, never stores a workspace URL or token, and every call is stateless (nothing survives between requests except what you see in the Output log). If you close the tab, nothing about your Databricks account is remembered anywhere.

### CLI requirement

Deploying needs the [Databricks CLI](https://docs.databricks.com/dev-tools/cli/) installed and at least one profile configured in `~/.databrickscfg` (`databricks configure`, or a profile added by hand). If the CLI isn't on your `PATH`, every Databricks-backed control on this tab (and the secret-scope / UC service-credential pickers in Authentication) shows an inline message with the install link instead of failing silently — export and preview keep working either way, since they never touch the CLI. Deploying a bundle project separately needs [`uv`](https://docs.astral.sh/uv/) on the machine running `databricks bundle deploy` — that's what builds the wheel `src/<pkg>` ships as (see [Project bootstrap](#project-bootstrap) below).

### Profile → catalog → schema

1. **Profile** — populated from your `~/.databrickscfg` section names. Picking a profile here is shared with the secret-scope pickers in the Authentication section (see [Secrets](#secrets) below), so you only choose it once.
2. **Catalog** — Unity Catalog catalogs visible to that profile (`databricks catalogs list`), loaded once a profile is picked.
3. **Schema** — schemas within the chosen catalog (`databricks schemas list`), loaded once a catalog is picked.

Each dropdown resets and reloads whenever the one before it changes, since a catalog/schema list only makes sense for its parent profile/catalog. An empty profile list means no `~/.databrickscfg` profile was found — a **retry** link is offered.

Unlike catalog, the schema doesn't have to exist yet — a pipeline can create its target schema on deploy. Picking **Custom schema… (create new)** at the bottom of the Schema dropdown swaps it for a text field where you type the new schema's name; **Back to list** returns to picking an existing one.

### Project bootstrap

Fill in a **Project name** (defaults to the connector's table name) and a **Project directory** (defaults to `~/polymo-projects`), then click **Bootstrap**. This writes a full bundle project to `<project directory>/<project name>`:

```
<project>/
  databricks.yml            # bundle + a `whl` artifact (built via `uv build --wheel`
                             # at deploy time) + one Lakeflow Declarative Pipeline
                             # resource, wired to the catalog/schema you picked
                             # (profile is passed separately, at deploy time)
  pyproject.toml            # packages src/<pkg> as that wheel (uv_build backend)
  src/<pkg>/__init__.py
  src/<pkg>/client.py        # the fetch/pagination/schema code — byte-identical to
                             # the first half of the Generated Code pane's script
  src/<pkg>/source.py        # the <PascalCase(pkg)>Source data source and reader
                             # (e.g. maileon_contacts -> MaileonContactsSource),
                             # built on <pkg>.client via a relative import
  pipelines/<stream>.py      # thin: imports <pkg>.source's DataSource class, then
                             # the @dp.table wiring
  README.md                  # what this project is, how to deploy/run it, where the
                              # table lands
  .polymo-bundle.json         # small manifest the Run button reads back (pipeline
                               # resource key) — not meant to be edited by hand
  .gitignore                  # excludes .polymo-bundle.json, .idea/, dist/, and
                               # other local/derived state from your own repo
```

`src/<pkg>/client.py` is never a re-derived or hand-simplified copy of the exported script — it *is* the same `generate_core()` output, so the bundle project can never drift from what the Generated Code pane and the Preview panel show you.

The DataSource class in `src/<pkg>/source.py` is named after the connector, not a generic `RestSource` — this is what shows up in Spark UI/logs and makes multiple bundled connectors easy to tell apart.

**The package reaches every executor via a wheel, not by-value pickling.** `databricks.yml` declares a `whl` artifact (`artifacts.default.build: uv build --wheel`) built from the root `pyproject.toml`, and the pipeline resource's `environment.dependencies` installs that built wheel — so `src/<pkg>` is importable on the driver *and* every executor, and `pipelines/<stream>.py` just does a plain `from <pkg>.source import <Class>`. Deploying needs [`uv`](https://docs.astral.sh/uv/) on the machine running `databricks bundle deploy` (it builds the wheel). The pipeline resource runs `serverless: true`; a classic-cluster pipeline would need the built wheel added as a cluster library instead of relying on `environment.dependencies`.

**Overwrite semantics are file-scoped, not directory-scoped.** Bootstrapping into a non-empty directory is refused by default; checking **Overwrite bundle files in existing folder** lets it proceed, but it only overwrites the bundle files listed above — anything else you've added to that project directory (a `.git` folder, notes, other pipelines, local CLI state) is left untouched.

### Deploy and Run

Once bootstrapped, **Deploy** runs `databricks bundle deploy -t dev` with the project directory as its working directory and your chosen profile, and **Run** runs `databricks bundle run <pipeline> -t dev` — enabled only after a successful deploy. Both can legitimately take a while (cluster startup, pipeline updates), so they're allowed to run for several minutes before timing out. Every command's combined output (or error) is appended to the **Output** log at the bottom of the tab, most recent last.

Changing the project name or directory after a successful bootstrap clears the remembered project path, so Deploy/Run re-disable until you bootstrap again at the new location — this avoids accidentally deploying a stale bundle.

The `-t dev`/`-t prod` **target** in `databricks.yml` controls Lakeflow's development-vs-production pipeline mode; the Deploy tab always deploys/runs the `dev` target, and `-t prod` is available by running the CLI yourself against the bootstrapped project directory once you're ready to promote it.

### Secrets

Every secret-bearing auth field (Bearer token, API key, OAuth2 client secret) has a **Secret source** toggle right below it:

- **Enter for preview / placeholder in export** (default) — the value you type is used only for previews in this browser session; it is never saved to disk, and the exported script/bundle gets a `REPLACE_ME` placeholder constant for you to fill in (or wire up to a secret store) after the fact.
- **Databricks secret scope** — pick a **Secret scope** and **Secret key** instead of typing a value. The scope/key dropdowns are populated from `databricks secrets list-scopes` / `list-secrets` for whichever profile you picked in the Deploy tab (pick a profile there first if you haven't). Scopes backed by an external store — Azure Key Vault-backed scopes, for example — show up automatically too, since the CLI lists them the same way as Databricks-backed scopes. Only the reference (`{scope, key}`) is written into the config and the generated code; the exported/bundled script resolves the actual value on the driver via a generated `_dbx_secret(scope, key)` helper at pipeline run time — see [Databricks secret-scope references](config.md#databricks-secret-scope-references) for the full mechanics. You can still type a value in the field above the toggle while in this mode; it's used only for previewing, same as the inline mode.
- **UC credential (Key Vault)** — resolve the secret through a Unity Catalog service credential instead: pick a **UC service credential** (populated from `databricks credentials list-credentials --purpose SERVICE` for the Deploy tab's profile, with a **Custom credential name…** option — like the Deploy tab's **Custom schema…** — for a credential the CLI can't list, or doesn't exist yet), then fill in the **Key Vault URL** and **Secret name**. Only the reference (`{credential, vault_url, secret_name}`) is written into the config; the exported/bundled script resolves the actual value on the driver via a generated `_uc_secret(credential, vault_url, secret_name)` helper — see [UC service-credential secret references](config.md#uc-service-credential-secret-references) for the full mechanics. Mutually exclusive with the Databricks secret scope mode — switching to one clears the other. You can still type a value in the field above the toggle while in this mode; it's used only for previewing, same as the inline mode.

Whichever mode you pick, a session token you *do* type for previewing can still be echoed back by a chatty API — see the redaction note at the end of [Previewing your connector](#previewing-your-connector) below for how the preview masks that.

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

An incremental connector previews as a *first run*: the preview reads no state file (not even one you point **State file or URL** at, so a remote `s3://` path needs no fsspec on your machine), sends the **Initial cursor value** if you set one, and never writes state — only the generated pipeline's `_Reader.read()` does that.

If the target API echoes your session token back in its response (an echo/debug endpoint, or a query-placed `api_key`), the preview masks it as `***REDACTED***` wherever it appears — in Records, DataFrame, and Raw API (payloads and URLs alike). This masking is best-effort: it matches the exact token substring plus the two URL-encoded forms `requests` itself would produce (so a token echoed back inside a query string, e.g. `raw_pages[*].url`, is still caught even if it contains characters like `+`, `/`, or `%`). A base64-encoded, hashed, or otherwise transformed copy of the token in the response won't be caught.

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
