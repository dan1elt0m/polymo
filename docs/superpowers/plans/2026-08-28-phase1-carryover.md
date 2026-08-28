# Phase 1 carry-over notes (deferred minors for Phase 2/3)

Source: SDD run of 2026-08-28-codegen-phase1.md (final review: mergeable; details in git history).

- Task 4: minor (deferred): offset docstring renders "/None" when limit_param unset (core.py.jinja offset branch)
- Task 4: minor (deferred): none-branch docstring wording drifted from brief ("(single page)")
- Task 5: minor (deferred): total_pages_header path has no execution test (structure/hygiene verified only)
- Task 7: minor (deferred, standing design trait): followed Link/next_url URLs keep session auth headers even cross-origin — consider host check in a later hardening pass
- Task 9: minor (deferred): oauth_extra dedicated behavior test only covers rendering; live form-encode of extra params untested end-to-end
- Task 10: minor (deferred): dp.py.jinja blank-line count differs between schema/no-schema variants (cosmetic)
- Task 11: minor (deferred): LAST_CURSOR max-tracking would TypeError on mixed int/str cursor_field values within one run (plan-mandated code; latent spec-level risk)
- Task 12: minor (deferred): windowed dp wiring not exercised on a live Spark cluster (hygiene+structure verified only)
- Task 13: minor (deferred): COLUMNS derivation breaks silently on nested/backtick DDL (plan-mandated line; silent nulls not crash)
- Task 13: minor (deferred): generated streaming _Reader lacks readBetweenOffsets override — checkpoint recovery replay would raise (plan-mandated template)
- Task 13: minor (deferred): empty-page no-advance = hot poll without an explicit processing-time trigger; document for users
- Task 14: minor (deferred): retry template renders literal booleans ("if not True or ...") — reads oddly; cosmetic cleanup candidate
- Task 14: minor (deferred): generated import order (requests before stdlib json/os) — cosmetic, ruff default rules don't flag
- Final: minor (deferred to Phase 2): incremental_mode with unset cursor_param/cursor_field renders None params (unvalidated config corner; pre-existing).
- Final: minor (deferred to Phase 2): reserved-name shadowing (stream named fetch_records etc.) has no guard in _identifier.
- Final: minor (deferred to Phase 2/3): windowed incremental STATE_PATH default is relative — executors read/driver writes; needs shared-storage default or doc; endpoints flat-shape deviation must appear in Phase 3 migration notes.
- Ruling to carry into Phase 3 migration notes: endpoints strategy emits flat records (no endpoint_name/data wrapper, unlike the 0.x runtime).
