# Verification

From the repository root:

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 -m unittest discover -s tests -v
python3 scripts/sync_mattpocock.py --check
python3 scripts/validate_adaptations.py
```

The offline suite tests the public sync, validation, and upstream-checker commands in disposable fixtures. It covers publication selection, additions, updates, removals, support-file changes, dirty Git protection, failure preservation, idempotence, per-skill baseline overrides, and checker exit precedence. Watcher tests exercise local state and mocked GitHub responses.

For updater changes, run a pinned real Matt import in a disposable clean Git repository using the installed npm CLI. Run it again with no changes and confirm `unchanged`. If the first run produces changes, review and commit them in that disposable repository before the second sync. Run a real read-only adapted upstream check separately.

CI runs the offline tests and structural catalog checks. Those checks do not reinstall skills or prove upstream byte identity. Static tests and disposable imports do not prove runtime discovery, model selection, permissions, or successful PR execution in a host agent.
