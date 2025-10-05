# Builder UI Walkthrough

If you are happiest filling out forms instead of wrangling YAML, the Builder UI is for you. It lives alongside Polymo and gives you a guided, visual way to design a connector from start to finish.

## Getting set up
1. Install the Builder extras: `pip install "polymo[builder]"`.
2. Start the local web app:
   ```bash
   polymo builder --host 127.0.0.1 --port 9000
   ```
3. Open the link shown in your terminal. Chrome, Edge, or any Chromium-based browser works best because they support the built-in file saving features.

> **Tip:** The command checks that PySpark 4 is present. If it is missing, the tool tells you how to install it before continuing.

## Landing screen options
When the page loads you will see three large tiles:
- **Start from scratch** – clears everything and opens the form with empty fields.
- **Upload YAML** – pick an existing config file to continue working on it.
- **Load an example** – try one of the sample connectors bundled with Polymo (GitHub, JSON Placeholder, etc.).

Every option resets old tokens, previews, and temporary values so you never accidentally reuse secrets. Under the tiles you will also see a **Saved connectors** library. The Builder automatically stores every change in your browser, so closing the tab or hopping back to the landing screen never loses your progress. Open an entry to keep editing, rename it to stay organised, export the YAML, or delete configs you no longer need.

## A guided form for your API
The left-hand panel has two tabs: **UI Builder** and **YAML Editor**. Stay on the UI Builder tab if you prefer plain-language fields. Each section can collapse to keep things tidy.

### 1. Connection basics
- **Base URL** – the root of your API, for example `https://api.example.com`. The builder checks that it looks like a valid URL.
- **Stream Path** – the specific endpoint, such as `/v1/orders`. Enter it exactly how you would type it in a browser.

### 2. Authentication (optional)
- Choose **None** if the API is public.
- Choose **Bearer Token** if you have a secret token. The value is stored only in your browser session and is never saved to disk.

### 3. Query parameters & headers
- Use the **Add Parameter** button to include filters like `status: active` or `_limit: 100`.
- Add headers the same way (for example `Accept: application/json`).
- You can use curly braces (`{user_id}`) inside the stream path. Matching parameters are filled in automatically.

### 4. Spark reader options
If your data pipeline supplies values at runtime (like `owner: dan1elt0m`), add them here. These options are shared with the preview and the final Spark call.

### 5. Pagination & incremental settings
- Pagination is currently either **None** (single request) or **Link header** (follow `rel="next"` links). Choose the one that matches your API’s behaviour.
- Incremental fields (`mode`, `cursor_param`, `cursor_field`) power actual incremental syncs. The panel also includes runtime inputs for the state file/URL, initial cursor value, and state key override—no need to type the Spark options separately. When you run the connector through Spark with `.option("incremental_state_path", ...)`, Polymo feeds the stored cursor into the query and writes the latest value back after the run. Paths can point to local files or remote URLs like `s3://...` (install `fsspec` for non-local schemes). Skip the path and the driver keeps the cursor in memory until the session ends; add `.option("incremental_memory_state", "false")` if you prefer to start fresh every time. The Builder records the fields in YAML; you still decide where the state lives at runtime.

### 6. Record selector (for nested responses)
Some APIs wrap data inside other objects. Use this panel to:
- Point to the right part of the response (e.g. `field_path: data → items`).
- Filter records with simple checks like “keep only items where `record.state == 'open'`”.
- Ask Polymo to cast values to the chosen schema so dates look like dates instead of plain text.

### 7. Schema tab
Switch to the **Schema** tab if you need to define the columns yourself. Otherwise leave **Infer schema** turned on and Polymo will guess from sample data.

## Editing YAML directly
Toggle to the **YAML Editor** tab if you enjoy working in text:
- The builder keeps the form and the YAML in sync. When you change something in one place, the other side updates after a short pause.
- Parsing errors are shown below the editor with helpful line numbers when available.
- If a change fails validation, you can revert to the last working version with a single click.

## Previewing your connector
The right-hand panel is where you test your work.

1. Click **Preview**.
2. The backend validates the config and makes the API call.
3. Pick a view:
   - **DataFrame** shows a tidy table you can page through (10–100 rows per page).
   - **Records** shows the same rows in raw JSON.
   - **Raw API** lists every HTTP call, including headers and any error message.
4. Adjust the **Limit** or **Page size** to control how much data is fetched for the preview.
5. Use **Copy Schema** to copy the column definitions to your clipboard if you want to paste them into docs or scripts.

If something goes wrong—wrong URL, missing token, network issue—the error appears in the status pill and the Raw API view so you can fix it quickly.

## Saving your work
- The Builder continuously caches your progress locally, so you can step away or experiment without fear—just reopen the connector from the library when you return.
- Use the connector picker in the header to jump between saved configs instantly; the **Manage connectors…** option opens the full library where you can rename, export, or remove drafts.
- When you are ready to download the file, press **Save** (or <kbd>Ctrl/Cmd</kbd> + <kbd>S</kbd>). Name the file in the modal; browsers that support folder access let you pick a target directory once, otherwise the file downloads like any other.
- Polymo always re-validates before saving to make sure you store a working configuration, and tokens are stripped automatically.

## Helpful touches
- The theme switcher toggles between light, dark, or “follow my computer” modes.
- The **Connectors** button in the header opens the saved connectors library—autosave means you never lose work when switching between configurations.
- The status pill keeps the latest validation, preview, or save result visible so you know what just happened.

That’s it—you now have a friendly workspace for building reusable API connectors without touching a single line of code.
