# Polymo 1.4: Databricks integration

Date: 2026-08-28. Approved by Daniel ("go") on the design presented in chat.

## What

Four connected features turning the builder into a deploy-capable tool:

1. **Project bootstrap as the primary export.** Exporting produces a
   Databricks Asset Bundle project (layout mirrors
   `databricks bundle init default-python`):

   ```
   <project>/
     databricks.yml            # bundle + pipeline resource; catalog/schema/target wired
     src/<pkg>/__init__.py
     src/<pkg>/client.py       # the SPECIALIZED typed fetch core (generate_core output)
                               #   + secrets helper — "helper code in src/"
     pipelines/<stream>.py     # thin: imports from <pkg>.client, defines RestSource
                               #   + @dp.table
     README.md
   ```

   The single-file export remains as a secondary option. One connector per
   project in v1.

2. **"Run on Databricks" in the builder.** The builder runs where the
   user's `databricks` CLI and `~/.databrickscfg` live; the backend shells
   out to the CLI. UI flow: pick profile → catalog → schema (dropdowns
   populated from the CLI), choose a project directory, then Bootstrap /
   Deploy / Run buttons with CLI output shown in the UI. Everything
   degrades gracefully when the CLI is missing or unauthenticated (clear
   error messages; export still works).

3. **Secrets from Databricks secret scopes.** Every secret slot (bearer
   token, API key, OAuth client secret, OPT_* option placeholders) can
   reference a secret scope + key (dropdowns via
   `databricks secrets list-scopes` / `list-secrets`). Configs carry ONLY
   the reference (`{"scope": ..., "key": ...}`), never values. Generated
   code resolves via a `_dbx_secret(scope, key)` helper (driver-side
   `dbutils`, with a clear RuntimeError outside Databricks). AKV-backed
   scopes appear automatically since the CLI lists them.

4. **Typed generated code** — shipped already in 1.3.0.

## Constraints

- Zero polymo imports in bootstrapped projects (the library in `src/` is
  generated, specialized code — polymo stays dev-time only).
- Secret VALUES never appear in configs, generated files, or server logs.
- CLI subprocess calls: JSON output (`-o json`), explicit `--profile`,
  timeouts, no shell string interpolation of user input (argv lists only).
- The builder never stores Databricks state; every CLI call is stateless.
- Bundle validation: `databricks bundle validate` must pass on a
  bootstrapped project (CI can't run it — verified manually/locally).

## Out of scope (v1)

Multi-connector projects; deploying loose single files; job (non-pipeline)
resources; workspace-file browsing; OAuth login flows for the CLI.
