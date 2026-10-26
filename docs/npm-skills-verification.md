# Matt Pocock sync

The updater reads the explicit `skills` array in the upstream publication manifest recorded in `sources.json`. Only published engineering and productivity subtrees are supported. Unlisted, experimental, and deprecated directories are not discovered.

## Commands

Requires Python 3.10+, Git, Node 22.20+, and the pinned npm dependency.

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 scripts/sync_mattpocock.py --check
python3 scripts/sync_mattpocock.py
python3 scripts/sync_mattpocock.py --revision FULL_40_CHARACTER_COMMIT_SHA
```

`--check` is an offline structural catalog check. It needs neither the npm CLI nor network access and does not verify byte identity against upstream.

For trusted local checkouts or synthetic fixtures, use `--source /path/to/source --revision FULL_40_CHARACTER_COMMIT_SHA`. The caller asserts that source's provenance. `SKILLS_CLI` can select another installed copy of `skills@1.7.4`.

## Replacement rules

A sync requires a clean Git index and worktree for its collection, source metadata, scripts, tests, dependencies, workflows, and maintenance docs. Uncommitted edits in that scope are refused, including prior sync output. Review and commit or stash changes before another sync.

The CLI copies each explicit source subtree into a disposable project with an isolated home and environment. It never runs upstream helper scripts or installs into a live agent. The updater checks the whole selected input and staged catalog and compares source/output bytes and modes before replacement.

Invalid or empty manifests, missing inputs, unsupported entries, CLI omissions, and fetch failures abort without pruning. Successful replacement owns only `skills/mattpocock/`, its retained publication manifest and license, and Matt's revision in `sources.json`. Complete validated selections determine removals.

Temporary directories honor `TMPDIR`. Staging and destination must support filesystem renames. Ordinary replacement errors restore moved targets; a process or host interruption during multi-path replacement can require manual inspection. Use Git to review and recover changes. There is no separate content-hash inventory.

## Automation

The Monday 09:17 UTC workflow runs tests, syncs, validates, and opens a review PR. It never auto-merges. Repository settings must allow Actions-created PRs. Token-created PRs may need maintainer-triggered checks to satisfy branch rules.
