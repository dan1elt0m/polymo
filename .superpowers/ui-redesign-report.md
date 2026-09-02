# Builder UI layout redesign — report

Branch: `worktree-agent-ad5d6d04d0ab36514` (isolated worktree, not pushed).
Scope: `builder-ui/` only; backend untouched. Static bundle rebuilt and committed.

## What changed, per approved point

### 1. Resizable, collapsible split (`components/SplitLayout.tsx`, `lib/layout.ts`)
- Config pane (left) and preview pane (right) sit in a `SplitLayout` with a 12px drag
  handle: pointer-capture drag, `role="separator"` with `aria-valuenow`, keyboard
  `←`/`→` (2% steps), `Home`/`End` (min/max), `Enter`/`Space` (collapse), double-click
  resets to the default ratio. Min widths: 400px config / 420px preview, re-clamped on
  window resize.
- One-click collapse (hover the handle → chevron button) turns the config pane into a
  44px rail with a vertical label and an expand button; the rail itself is the expand
  affordance.
- "Focus preview" toggle in the preview header hands the full width to the
  DataFrame/Records/Raw viewer (session-only, never persisted).
- Ratio + collapsed state persist under `polymo.layout.v1` (try/catch around
  storage, defaults `{ ratio: 0.46, collapsed: false }`, ratio clamped to 0.25–0.75).
- The app shell is now `h-screen` with both panes as flex columns; the preview viewer is
  `flex-1 min-h-0 overflow-auto` with a sticky table header, so the DataFrame fills the
  available height instead of a fixed ~250px box. The empty footer bar is gone.

### 2. Flattened form (`BuilderPanel`, `builder/ConfigurationTab`, `builder/SchemaTab`, sections/*)
- One card level: pane card → 20px padding → form. The nested `p-6` → `rounded-2xl`
  card → `p-8` stack and the inner Configuration/Schema tab strip are removed, which
  gives the form back ~100px of width at any split ratio.
- Two tiers: **Essentials** (Base URL; Stream path + Table name on one row; Response
  format (+ XML record path); Authentication) always visible. **Advanced** is a flat list
  of 40px `Disclosure` rows (chevron · title · mono one-line summary): Streaming table
  toggle, Schema, Pagination, Incremental sync, Partitioning, Error handling, Headers,
  Query parameters, Spark reader options, Record selector. Each keeps its existing
  auto-open-when-configured behaviour and summary text. Headers/Params/Reader options
  expose their "Add" action in the row header.
- Key/value rows (headers, params, reader options) are single-line `name | value | ×`
  grids instead of bordered two-field cards. All test ids preserved
  (`param-row-*`, `param-name-input-*`, `query-params-toggle`, `streaming-toggle`, …).
- No changes to atoms, validation, API calls or the `polymo.saved_connectors.v1` /
  `polymo.active_connector_id.v1` / `polymo.working_state.v1` keys.

### 3. Authentication redo (`sections/AuthenticationSection.tsx`)
- Auth type is a full-width segmented control (None · Bearer token · API key · OAuth 2.0),
  keyboard-navigable (`role="radiogroup"`).
- API key: Placement + Header/Query name on one row; secret input below with the
  "not saved" hint as helper text.
- Secret source is a labelled radio row that never wraps (`flex-nowrap`, short labels
  Preview only · Secret scope · UC credential); the selected option's explanation
  renders as one helper line underneath instead of being crammed into the pills.
- Workspace suggestions are one compact line: "Load from workspace: scopes · keys
  (or service credentials) · using profile [select]" — the Databricks profile select is
  the small inline select next to the loaders, with a single optional-profile note and
  inline error text. The grey-on-grey helper box is gone.
- Same loaders, same `databricksProfileAtom`, same datalists and field semantics.

### 4. Design system (`components/ui/primitives.tsx`, `styles/index.css`, `tailwind.config.ts`)
- One label style (`text-xs font-medium text-fg-muted`), one input height (`h-9`),
  one textarea/select style, one button set (primary / secondary / ghost / link /
  icon), `space-y-4` inside sections and `gap-6`/`gap-8` between tiers.
- Theme tokens as RGB-triplet CSS variables on `:root` (light) and `.dark`
  (Dracula-ish) mapped to Tailwind colours: `background`, `surface`, `field`, `raised`,
  `border(-strong)`, `fg`, `fg-muted`, `fg-subtle`, `accent(-hover/-fg/-text/-soft/-ring)`,
  `success`, `warning`, `error`. Components use them directly; the entire
  `.dark … !important` override layer in `index.css` is deleted. Inter + JetBrains Mono,
  the light palette, the Dracula dark palette and the ThemeMenu are kept.
- Muted text meets ~4.5:1 in both themes: `#65636d` on the light surface (5.2:1),
  `#a3abcc` on the dark surface (5.5:1); error red in dark raised to `#ff6b6b` (4.9:1).
- LandingScreen / CodePane / ThemeMenu / InfoTooltip had their colour classes mapped onto
  the tokens (mechanical, no layout change) because they relied on the removed overrides.
- Pane toolbars use CSS container queries (`.pane` is an inline-size container) so tab
  and button labels shorten and 3/4-column field grids fold to 2 columns when the *pane*
  gets narrow — independent of viewport width.
- The theme's effective mode is now React state (live OS theme change re-renders the
  ThemeMenu label and the fade), fixing a stale "System (light)" label seen while testing.

### 5. Deploy stepper (`components/DeployPanel.tsx`)
- Vertical five-step stepper: Profile → Target (catalog + schema incl. "Custom schema…")
  → Bootstrap (name, directory, overwrite, validation errors) → Deploy → Run. Each step
  shows done (filled check) / active (ringed number) / blocked (muted, with a "do X first"
  hint) — derived from the existing state; only a UI-side `lastRunOk` flag was added so
  the last step can show done.
- CLI output is docked full-width under the stepper in a mono panel that fills the
  remaining height, scrolls, auto-follows, and has a Clear button.
- Same endpoints (`listDatabricksProfiles/Catalogs/Schemas`, `bootstrapDatabricksProject`,
  `deployDatabricksBundle`, `runDatabricksPipeline`), same gating.

### Also
- Validation/preview errors now also render as a full-width error callout in the
  preview body (`preview-error-notice`), since the status pill truncates long messages.
- Empty preview state has a proper placeholder; the Records/Raw views use the pane's
  scroll container directly.

## Verification
- `npx tsc -b --noEmit` — clean.
- `npm run build` — `src/polymo/builder/static/main.js` (367 kB) + `main.css` (35 kB) rebuilt.
- There is no `npm test` script. The Playwright e2e specs under `builder-ui/tests` were
  not run: they pre-date this change and already reference elements that do not exist
  (`getByLabel('Stream Name')`), and the pinned Playwright Chromium build (1193) is not
  installed locally. Note that `preview.spec.ts`'s `getByText('Fetched 2 sample records')`
  strict locator was a useful check: an interim version rendered the status pill twice and
  would have broken it; the final build renders it once and reflows it via CSS.
- Backend `pytest`: 393 passed (run outside the sandbox because tests bind local sockets).
- Browser click-through against `uvicorn polymo.builder.app:create_app` on :8918 at
  1440×900 and 1100×800, light and dark: landing → Resume / Start from scratch →
  Authentication with API key + Preview only / Secret scope / UC credential → Preview
  against jsonplaceholder (10 rows, table fills the pane) → drag the split → collapse /
  expand → focus preview → Generated Code → Deploy tab.
- Screenshots (`.superpowers/ui-shots/`, 48 files, captured with
  `.superpowers/ui-shots.mjs`): `NN-<state>-<light|dark>-<1440|1100>.png` for
  01-landing, 02-builder-empty, 03/04/05-auth-apikey-{preview-only,secret-scope,uc-credential},
  06-preview-dataframe, 07-advanced-open, 08-split-dragged, 09-config-collapsed,
  10-focus-preview, 11-generated-code, 12-deploy-stepper.

## Issues found and fixed during verification
- Tab bar wrapped and "Save config" clipped when the config pane sat at its 400px floor
  → container-query short labels (Builder / Code / Save) with stable `aria-label`s.
- 4-column field grids (Error handling, Partitioning) wrapped their labels in a narrow
  pane → `.fields-4` / `.fields-3` fold to two columns below 580 / 520px pane width.
- Width overrides such as `w-20` lost to the base `w-full` → use `max-w-*`.
- Status pill was squeezed to "Fetc…" in a narrow preview header → drops to its own line
  under the title below 680px pane width.

## Not done / notes
- Landing page, Generated Code pane internals and the backend are untouched beyond the
  mechanical colour-token mapping.
- The stale Playwright e2e specs were left as they are (out of scope); they need
  updating to the current field labels before they can pass.
- The Deploy stepper's done/active/blocked states were verified without a Databricks
  profile selected (no workspace calls were made from this session).
