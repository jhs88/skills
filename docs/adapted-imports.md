# Adapted Tstack and Pstack imports

This repository contains 11 deliberately adapted skills, not exact upstream mirrors. The immediate inputs were the owner's dirty Pi working tree. No source files were changed, no skills were installed, and no runtime compatibility beyond source packaging was tested.

## Ownership and provenance

- `skills/tstack/` contains `babysit-pr`, `council`, `file-pr`, `full-send`, `full-stop`, `leaving-pr-comments`, `modernize`, `sol-loop`, and `takeover`.
- `skills/pstack/` contains `technical-writing` and `unslop`.
- The 11 skill prompts and three watcher support files total 14 imported files. The watcher helper retains its executable mode and exact upstream bytes.
- `adaptations.lock.json` is independent of the Matt importer and its lock. It records the Pi repository, HEAD, source-document hashes, exact working-tree input hashes, destination hashes, and upstream collection baselines.
- Pi HEAD `39569d27e16029f16dff397acc1f2fbffeba1349` identifies the source checkout, not a committed snapshot of the imported content. Some inputs were modified or untracked. The per-file input hashes describe what was actually copied.
- The Tstack upstream pin is `7de017b3fc9d50c03cf3ecb98fb71e0ca65a78bd` from `https://github.com/t3dotgg/tstack`.
- Pstack `technical-writing` uses `bdf7aa355337897f167153e05069aca505dae17c`; `unslop` uses `fd6dd6f7276956a532bb78a748a8d2818b6eb5f4` from `https://github.com/cursor/plugins`.

The original upstream collection hashes are separate from the local source and destination hashes. The Pstack collection baseline uses the `unslop` revision, with the entire `technical-writing` subtree explicitly overridden to its own revision. This also lets the checker identify new or deleted upstream skills without importing them. Pstack automations and other plugin directories are outside the checker's selection.

Licenses were fetched from the exact first-party pins, not inferred from public visibility. Tstack's `LICENSE` and both pinned copies of `pstack/LICENSE` matched the corresponding MIT text in Pi's third-party notices. Full notices and attribution live in `third_party/tstack/` and `third_party/pstack/`. Keep those directories with redistributed imports. Upstream MIT notices do not assign an unapproved new license to the owner's local additions, checker, tests, or documentation. Publication approval remains separate.

## Adaptation log

Only these prompt changes were made after copying the Pi working-tree versions:

| File | Change | Reason |
| --- | --- | --- |
| `skills/tstack/council/SKILL.md` | Replaced the workstation-specific provider routing sentence with discovery through the runtime's existing configured GPT subscription connection. | No provider alias or local proxy dependency belongs in a shared skill. The three GPT model IDs, no-substitution rule, fresh contexts, and existing-subscription requirement remain intact. |
| `skills/pstack/technical-writing/SKILL.md` | Replaced the Pi slash-command spelling in the description with explicit skill invocation wording. | Use each runtime's supported invocation mechanism. The manual-only `disable-model-invocation: true` intent remains intact. |

All other imported bytes match their immediate Pi source hashes. All support files present in those source skill directories were retained except generated `__pycache__` bytecode, which is excluded explicitly in the manifest. In particular, `babysit-pr/scripts/pr-wait`, `references/watcher-limitations.md`, and `references/bot-triage.md` are present. Upstream agent metadata absent from the Pi adaptations was not invented or restored.

The updater was adapted from Pi's read-only checker, not used as an overwrite mechanism. Changes generalize its source inventory to both collections, verify mixed Pstack pins and licenses, keep partial successful reports when another source fails, and ignore unrelated plugin commits when deciding whether collection content changed. It retains exact-revision validation, full support-file hashing, temporary bare Git fetches, no upstream execution, and distinct status codes. Offline tests reuse the source checker's comparison cases and watcher behavior cases. Source hashes identify both test inputs.

## Portable integration and limits

This is a source catalog, not a new provider, installer, or workflow engine. Load only the skills you intend to use through the target runtime's documented skill loader. No live installation, per-runtime catalog refresh, or model invocation was performed here. A host that ignores manual-only metadata must preserve that intent in its own integration before enabling `technical-writing`.

The PR skills require a Git checkout and authorized GitHub tools. The optional `pr-wait` fallback requires Python 3.10+, the `gh` CLI with an existing authorized connection, and a POSIX runtime because the pinned helper uses `fcntl`. It writes its own lock and event state under `~/.local/state/pr-wait/` only when invoked. Its help text names one possible monitor integration, not a required host. Do not run it as part of an upstream check.

Use native advertised model discovery, delegation, watcher, process, and question tools only when the runtime actually exposes them. Council keeps `gpt-6.1-sol`, `gpt-6-astra`, and `gpt-6-luna`; if a required model or per-child selection is unavailable, report the blocker instead of substituting or configuring another subscription. Native T3 watchers are optional and used only when exposed. Otherwise the included helper is the fallback, with its limitations and independent merge verification intact.

`full-send` remains explicit end-to-end task authorization, `full-stop` never merges, and normal runtime/system approval prompts still apply. Vendoring these prompts is not authorization to commit, push, comment, merge, run a watcher, or change external systems during repository maintenance.

No Uncle Bob agent-gauntlet skill, prompts, roles, or workflow pipeline was imported. Other inspected Pi skills are deferred:

| Candidate | Decision and reason |
| --- | --- |
| `code-navigation` | Defer. Depends on the Pi MCP configuration, exact exposed navigation tools, codemode discovery, and child-profile permissions. |
| `tilth` | Defer. Assumes an installed CLI and imposes global tool preferences. It is not a dependency of the selected prompts. |
| `subagents` | Defer. Binds to Pi's extension schemas, model discovery command, configured agent types, and fallback behavior. Its separate upstream provenance also needs its own integration review. |
| `compare-prototypes` | Defer. Requires Pi-specific `scout` and `build` agent types and can route into the excluded role pipeline. No such dependency is needed for these imports. |

## Read-only upstream checks

Requires Python 3.10+ and Git. Tests and validation are offline; the update checker fetches public upstream Git objects without credentials or running upstream code.

```sh
python3 -m unittest discover -s tests -p 'test_adapt*.py' -v
python3 scripts/validate_adaptations.py
python3 scripts/check_adapted_updates.py
python3 scripts/check_adapted_updates.py --json
```

The checker returns `0` when collection files and licenses are unchanged, `1` for updates, and `2` for an invalid baseline, fetch failure, or another incomplete check. Failure takes precedence over detected updates. It reports new, deleted, and modified skills and every added, deleted, or changed support file. `repository_changed_files` is scoped to the collection and license and compares the primary collection pin; per-skill overrides are authoritative for the file-level classifications. Unrelated repository commits alone do not require reconciliation. An empty or unsupported inventory fails closed.

`.github/workflows/check-adapted-upstreams.yml` runs Mondays at 09:41 UTC and supports manual dispatch. It has only `contents: read` permission, tests and validates the adaptations first, and prints a literal-text report in its job logs and step summary. Updates and failures make the job fail with their distinct exit status. It creates no issues or PRs, uploads no artifacts, and never rewrites skills or pins. The checkout action's exact SHA was verified against its canonical GitHub repository. The hosted workflow itself has not been run.

When updates appear, a human must review the pinned-to-main diff, licensing, local adaptations, support code, and permission boundaries. Reconcile deliberately, then update both input provenance and destination hashes and rerun tests. Do not point a generic automatic sync or install command at these adapted directories. Newly reported Pstack skills are candidates for a separate selection decision, not authorization to import them.

The captured [network report](adapted-upstream-check.json) found Tstack current at its pin. Pstack main was `99b609a72323b70204eab407c622f436e858e112`, with changes to both imported prompts, `technical-writing` and `unslop`. Its wider collection had 14 new skills, no deleted skills, and 42 modified skills. The file-level report includes support files. The checker returned `1` for updates, with no check failures. These updates were reported, not imported.

The Matt updater and its workflow are independently owned. This importer does not change their content, lock, or behavior.
