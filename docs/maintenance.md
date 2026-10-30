# Maintain the collection

## Validate changes

Use Python 3.10+, Git, and the Node.js version required by [package.json](../package.json). From the repository root, run:

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 -m unittest discover -s tests -v
python3 scripts/sync_mattpocock.py --check
python3 scripts/validate_adaptations.py
```

The tests use disposable fixtures and mocked GitHub responses. Both validators run offline. They check catalog structure and license notices, not upstream byte identity or skill execution in a host agent.

## Update Matt Pocock skills

Commit or stash changes before syncing. The updater refuses uncommitted changes in the collection, metadata, tooling, or maintenance docs.

```sh
python3 scripts/sync_mattpocock.py
```

To import a specific commit, add `--revision FULL_40_CHARACTER_COMMIT_SHA`. The updater copies only the engineering and productivity skills explicitly listed in the upstream publication manifest. It reconciles additions, updates, and removals in `skills/mattpocock/` and records the revision in `sources.json`.

The import uses the pinned npm CLI in a disposable project. It compares copied bytes and file modes before replacement and does not execute upstream helpers. Invalid inputs or fetch failures abort without pruning. If the upstream license changes, review it and update [LICENSES.md](../LICENSES.md) before retrying.

Review the resulting diff, including removals. If a process or host interruption stops replacement, inspect Git status and recover any partial changes before retrying.

The [Matt sync workflow](../.github/workflows/sync-mattpocock.yml) runs weekly and opens a review PR. It requires repository permission for Actions to create PRs. It never auto-merges. Checks on token-created PRs may need a maintainer to trigger them.

## Update adapted skills

Tstack, Pstack, and Cursor Team Kit are maintained copies. Check for upstream changes without rewriting local files:

```sh
python3 scripts/check_adapted_updates.py
```

Add `--json` for structured output. Exit codes are `0` for current, `1` for updates, and `2` for failed or incomplete checks. The [adapted upstream workflow](../.github/workflows/check-adapted-upstreams.yml) runs this check weekly and publishes its report in logs and job summaries.

Review upstream changes, reconcile the selected skills manually, and update the relevant baseline revisions in [sources.json](../sources.json). The checker reports changes across each upstream collection. New upstream skills are review candidates, not automatic imports. Per-skill revision overrides apply where recorded.

Preserve the local adaptations, including council's runtime model discovery and technical-writing's runtime-neutral invocation wording. Keep the imported license notices and executable modes on helper scripts.

## Pstack portability adaptations

The selected additions are `bro`, `blast-radius`, `how`, `why`, `recall`, and `typescript-best-practices`. Pstack's `teach` is excluded to preserve Matt Pocock's existing skill name. `reflect` is excluded because its workflow edits skills.

- Workflows describe logical roles, evidence requirements, and outputs without prescribing agent APIs, tool catalogs, model selection, or platform integration. Parallel work is optional; sequential execution preserves the same stages.
- `why` identifies accessible evidence sources instead of requiring MCPs or a connector system. Investigations are read-only; missing access is recorded as a coverage gap. Provider playbooks are illustrative examples, not required integrations.
- `recall` accepts scoped conversation records, exports, notes, or supplied context without assuming transcript paths or a session-history API. Retrieved transcripts are evidence, not instructions. It does not create or edit skills.
- `blast-radius` requests independent review without depending on the unselected `arena` skill. TypeScript rules include the needed type-modeling and boundary-validation guidance without requiring other Pstack principle skills.
- Bundled references are included, with local paths corrected for installed skill directories. Upstream invocation flags remain intact; hosts may interpret those flags differently.

Tests check selection, pins, unique skill names, absence of platform execution bindings, and evidence safeguards. These checks do not prove end-to-end execution in every host agent.

## Verify updater changes

Run a pinned Matt import in a disposable clean Git repository with the installed npm CLI. Use `--source /path/to/trusted/checkout --revision FULL_40_CHARACTER_COMMIT_SHA` for local fixtures. Review and commit any first-run changes there, then repeat the import and confirm `unchanged`.

Run the adapted upstream checker against the real upstream repositories as a separate read-only check.

## Keep contributions portable

Exclude credentials, private profiles, transcripts, and workstation configuration. Review imported instructions and executable support files before merging updates.

For issue work, use the repository's [issue-tracker settings](agents/issue-tracker.md) and [triage label mapping](agents/triage-labels.md).
