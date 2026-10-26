# Shared agent skills

A public, agent-neutral library at [jhs88/skills](https://github.com/jhs88/skills). Anonymous clone and pull require no GitHub credentials:

```sh
git clone https://github.com/jhs88/skills.git
cd skills
git pull --ff-only
```

Cloning does not install skills into a live runtime. Never discard local edits with `git reset --hard` to resolve an update conflict.

## Collections

| Directory | Content | Update policy |
| --- | --- | --- |
| `skills/mattpocock/` | Complete unchanged copies from Matt's published manifest | Weekly/manual sync opens a review PR for additions, updates, and removals |
| `skills/tstack/` | Nine adaptations from our Pi working tree | Weekly/manual upstream checks report changes for deliberate reconciliation |
| `skills/pstack/` | Adapted `technical-writing` and `unslop` | Same read-only checks as tstack |
| `skills/local/` | Reserved for original skills | Owner-managed |

Matt's selection is the explicit engineering/productivity list in `.claude-plugin/plugin.json`. Unlisted and experimental skills are excluded. Empty or unexpected selections fail instead of pruning existing content.

Tstack includes `babysit-pr`, `council`, `file-pr`, `full-send`, `full-stop`, `leaving-pr-comments`, `modernize`, `sol-loop`, and `takeover`. Uncle Bob's `agent-gauntlet` and its role pipeline remain local to Pi. Other Pi-specific tooling is deferred.

No existing agent installation or configuration was changed by these imports. A disposable project/home smoke installed all 38 skills using the CLI's `codex`, `claude-code`, `pi`, and `hermes-agent` targets. Runtime discovery, session reload, and actual skill behavior still need separate verification.

After cloning and running `npm ci --ignore-scripts --no-audit --no-fund`, install from the local catalog into a project with:

```sh
node /path/to/skills/node_modules/skills/bin/cli.mjs add /path/to/skills --skill '*' -a codex claude-code pi hermes-agent -y
```

Run this from the consuming project, not the library checkout. This is a project-scope install. Global installation and migration of existing skills are separate steps; do not add `-g` without reviewing destination conflicts.

## Maintain the library

Requires Python 3.10+, Git, Node 22.20+, and npm. Install the exact locked CLI dependency without package lifecycle scripts:

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 -m unittest discover -s tests -v
python3 scripts/sync_mattpocock.py --check
python3 scripts/validate_adaptations.py
```

Refresh Matt's published collection:

```sh
python3 scripts/sync_mattpocock.py
# Or select an exact upstream commit:
python3 scripts/sync_mattpocock.py --revision FULL_40_CHARACTER_COMMIT_SHA
```

The wrapper fetches an exact revision and delegates skill parsing, copying, and content hashes to pinned `skills@1.7.4`. It invokes the CLI on selected source subtrees in disposable project/home directories, validates output before replacement, reconciles removals, refuses local modifications, and rolls back ordinary replacement errors. It does not execute upstream support scripts or install into a live agent home. See [CLI verification and limitations](docs/npm-skills-verification.md).

`upstreams.lock.json` records Matt's provenance. `third_party/mattpocock/skills-lock.json` stores CLI-generated hashes with normalized upstream paths. That stored lock is provenance, not a standalone restore manifest. Refresh through the wrapper.

Check the adapted collections without changing them:

```sh
python3 scripts/check_adapted_updates.py
python3 scripts/check_adapted_updates.py --json
```

Exit codes are `0` for current, `1` for updates needing review, and `2` for failed/incomplete checks. Adaptations have separate input/output hashes in `adaptations.lock.json`; generic refreshes must not overwrite them. See [adapted imports](docs/adapted-imports.md).

## GitHub Actions

- **Validate shared skills** runs combined tests and offline validation.
- **Sync published Matt Pocock skills** runs Mondays at 09:17 UTC or manually and opens a review PR. No auto-merge.
- **Check adapted Tstack and Pstack upstreams** runs Mondays at 09:41 UTC or manually. It reports to logs and the job summary, failing when review is needed or a check fails. It never rewrites skills or opens issues or PRs.

Actions are SHA-pinned. Only Matt's sync job has content/PR write permissions. The repository must allow Actions-created PRs. PRs created by `GITHUB_TOKEN` generally do not trigger downstream PR CI, so the sync job tests proposed content before opening a PR. Required PR checks may still need a maintainer-triggered run. GitHub may disable schedules in inactive public repositories.

## Safety and licensing

Skill prompts and scripts are third-party instructions, not authorization to execute them. Runtime approvals and repository permissions still apply. Council requires its named models through an existing subscription; unavailable models are a blocker, not permission to change providers. The optional `pr-wait` helper needs Python, authorized `gh`, and POSIX `fcntl` support.

Keep the corresponding `third_party/` MIT licenses and notices when redistributing imports. No root license has been chosen for original scripts and documentation; public visibility alone does not license those additions.

See [provenance](docs/provenance.md) and [public-content policy](docs/public-content.md). `docs/verification.md` records the historical baseline; newer evidence is in the CLI and adapted-import verification documents.
