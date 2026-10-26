# Shared agent skills

A reviewable source repository for shared agent skills. The first baseline copies Matt Pocock's published skills without editing their contents. No skills have been installed into a live agent runtime by this project.

The intended public repository is `jhs88/skills`. After publication, anyone can clone or pull over HTTPS without GitHub credentials:

```sh
git clone https://github.com/jhs88/skills.git
cd skills
git pull --ff-only
```

Do not use `git reset --hard` to resolve update conflicts. Stop and review local edits, then commit, stash, or reconcile them explicitly. Publication and live installation are separate approval steps.

## What's included

- `skills/mattpocock/<slug>/` contains complete, byte-for-byte copies of each selected skill, including support files.
- `skills/local/README.md` reserves a separate home for future local skills. It is not a skill directory.
- `third_party/mattpocock/` preserves upstream's MIT license and plugin manifest.
- `upstreams.lock.json` records the upstream commit, manifest hash, selected source paths, per-file SHA-256 hashes, and skill tree hashes.

Only the explicit `skills` array in upstream `.claude-plugin/plugin.json` selects content. Every entry must match `./skills/engineering/<slug>` or `./skills/productivity/<slug>`. Unlisted directories, including experimental skills, are excluded. Unexpected layouts, empty manifests, duplicate names, missing entry files, special files, and symlinks fail closed.

These are real upstream copies, not rewritten summaries or imports of locally customized skills. Pstack, tstack, other upstreams, and private workstation configuration are out of scope.

## Refresh and validate

Requires Python 3.10+ and Git. The updater uses only the Python standard library. Tests and offline validation need no GitHub credentials or network access.

```sh
python3 -m unittest discover -s tests -v
python3 scripts/sync_mattpocock.py --check
python3 scripts/sync_mattpocock.py
python3 scripts/sync_mattpocock.py --revision FULL_40_CHARACTER_COMMIT_SHA
```

The normal updater resolves upstream HEAD once, fetches that exact commit in a temporary clone under `TMPDIR`, and copies only selected files. It never runs upstream scripts. For a trusted local checkout or fixtures:

```sh
python3 scripts/sync_mattpocock.py --source /path/to/upstream-checkout
python3 scripts/sync_mattpocock.py --source /path/to/fixture --revision FULL_40_CHARACTER_COMMIT_SHA
```

With `--source`, the caller owns checkout cleanliness and provenance. Without an explicit revision, Git HEAD supplies the revision. Fixture callers can assert a revision explicitly; this does not verify that their bytes came from that commit. Production automation uses the network path instead.

The updater stages and validates all new content before replacing managed outputs. Fetch and validation failures leave the existing skill copies and lock untouched. Ordinary installation errors roll back all three managed targets. Additions, changes, and removals reconcile only `skills/mattpocock/`, `third_party/mattpocock/`, and `upstreams.lock.json`; local skills remain untouched. Existing managed content must pass its lock before updating, so local modifications cause a failure instead of silent overwrite. Unchanged input is a no-op, including file modification times.

A direct sync is intentional. A generic `npx skills update` command is not the contract for reconciling this repository's authoritative published allowlist, deletions, complete support files, license, and provenance lock. No package installer runs during sync.

## Weekly review PRs

`.github/workflows/sync-mattpocock.yml` runs Mondays at 09:17 UTC and supports manual dispatch. It opens or updates `automation/mattpocock-skills` with a human-review PR. No automatic merge is configured. The sync job alone receives `contents: write` and `pull-requests: write`; other jobs have read-only repository permission. Third-party actions are pinned to verified full commit SHAs.

Before enabling this after publication, enable **Settings > Actions > General > Workflow permissions > Allow GitHub Actions to create and approve pull requests**. This workflow creates PRs but does not approve them. Organization policy can block the setting. Scheduled workflows run from the default branch and may be disabled by GitHub after inactivity in public repositories.

CI runs tests and offline lock validation on pushes, PRs, and manual dispatch. GitHub generally does not trigger another workflow for PR events created by `GITHUB_TOKEN`. The sync job therefore runs the tests and validation before opening its PR. Required PR checks may still need an authorized maintainer to run CI manually or trigger a permitted event; no PAT or GitHub App token is configured here. Neither workflow has been run on GitHub yet.

## Runtime and security boundaries

This repository is a source catalog, not an installer. No compatibility claim is made for every agent runtime. Choose skills, inspect their instructions and executable support files, then use your runtime's documented discovery or installation mechanism separately. Vendoring does not authorize executing support scripts or issuing tracker writes requested by a skill. Upstream prompts can request tools, network access, package installs, and issue operations; normal user approvals still apply.

The updater serializes writers with `.sync-in-progress` and refuses stale guards. Inspect an interrupted run before removing a stale guard. Rollback covers ordinary process errors, not power loss or a forcibly killed process during the multi-path replacement. Do not run another writer concurrently.

## Ownership and licensing

Matt Pocock's copied material remains under its upstream MIT terms. Keep `third_party/mattpocock/LICENSE` when redistributing it. This repository does not assign a new license to Joe's local work. Licensing for local scripts and documentation is pending owner approval; public visibility alone is not permission to reuse that material.

See [provenance](docs/provenance.md), [public content policy](docs/public-content.md), and [verification](docs/verification.md). Agent workflow settings live under `docs/agents/`.
