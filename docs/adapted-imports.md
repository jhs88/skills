# Adapted collections

The selected Tstack and Pstack skills are maintained copies, not automatic mirrors. `sources.json` records their upstream repositories, collection paths, selected names, and baseline revisions. Pstack's `technical-writing` has a separate revision override. Git records the maintained content and edits.

Council uses runtime-provided model discovery. Technical writing uses runtime-neutral invocation wording. The included `pr-wait` helper retains its imported bytes and executable mode. Keep each collection's license and attribution under `third_party/`.

## Check for updates

```sh
python3 scripts/validate_adaptations.py
python3 scripts/check_adapted_updates.py
python3 scripts/check_adapted_updates.py --json
```

Validation checks the selected local catalog, frontmatter, readable support files, local references, and licenses. It does not compare content hashes or run the skills.

The checker fetches only adapted sources into disposable Git repositories. It reconstructs baseline and current inventories directly from Git, applies per-skill baseline pins, and reports added, removed, or changed skills, support files, modes, and licenses across each upstream collection. New upstream skills are review candidates, not new selected imports. No local files or pins change.

Exit codes are `0` for current, `1` for updates, and `2` for failed or incomplete checks. Failure takes precedence over available updates. The Monday 09:41 UTC workflow publishes logs and job summaries. Review changes manually, reconcile maintained content, and update the relevant pins in `sources.json`.

## Runtime requirements

PR workflows need Git and authorized GitHub tools. The optional `pr-wait` helper needs Python 3.10+, `gh`, and POSIX `fcntl`. It stores state in `~/.local/state/pr-wait/` when invoked. See its [limitations](../skills/tstack/babysit-pr/references/watcher-limitations.md).

Council requires its named GPT models and per-delegate model selection. The host agent controls invocation and approval. Static validation does not prove those capabilities work.
