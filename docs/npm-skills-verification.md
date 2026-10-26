# npm skills sync verification

## Supported commands

Requires Python 3.10+, Git, and Node 22.20.0 or later. The verified runtime was Node v22.23.4 with npm 10.9.9. `package.json` pins `skills` to 1.7.4, and `package-lock.json` pins its dependency graph and registry integrity values.

```sh
npm ci --ignore-scripts --no-audit --no-fund
python3 -m unittest discover -s tests -v
python3 scripts/sync_mattpocock.py --check
python3 scripts/sync_mattpocock.py
python3 scripts/sync_mattpocock.py --revision 5beb35b040e3de97e54fa9e386d7e42d15c295c2
```

Tests and `--check` require the installed CLI but do not fetch dependencies or upstream content. Sync never invokes npm or npx. For a disposable toolchain outside this checkout, set `SKILLS_CLI` to the absolute path of that installation's `node_modules/skills/bin/cli.mjs`. The wrapper checks the installed package name and version before using it.

## Responsibility split

The Python wrapper resolves and fetches an exact upstream commit, validates `.claude-plugin/plugin.json`, and selects only its explicit engineering and productivity paths. It rejects empty selections, unexpected paths, duplicate names, symlinks, special files, and a missing or changed MIT license marker.

Each selected subtree is passed to the installed npm CLI with the tested command shape:

```sh
node /path/to/node_modules/skills/bin/cli.mjs add /path/to/upstream/skills/engineering/code-review --skill code-review -a codex -y --copy
```

Using exact subtrees matters. Repository-wide discovery can find unpublished directories or another skill with the same frontmatter name. The CLI owns skill parsing, installation, support-file copying, and content hashes. The wrapper compares its staged output against the complete selected source inventory before accepting it. If the CLI omits or changes a file, sync fails rather than silently changing the byte-copy contract.

The wrapper then reconciles the owned Matt subtree, including removals, with rollback on ordinary replacement failures. It retains the writer guard and refuses modified, added, or deleted managed files. Unchanged output preserves file modification times. Other skills and adaptation locks are not managed by this updater.

Every CLI invocation gets a disposable project directory, HOME, XDG directories, and temporary directory. Only PATH is inherited. `DISABLE_TELEMETRY=1` and `DO_NOT_TRACK=1` disable telemetry and security-audit requests. There is no global installation flag, live agent directory, or upstream script execution.

## Locks and offline validation

`upstreams.lock.json` now contains only the upstream repository, revision, installer identity, and manifest/license SHA-256 values. The previous custom per-file and per-tree hash engine is removed.

`third_party/mattpocock/skills-lock.json` retains the CLI's project lock schema and `computedHash` values. The wrapper normalizes only each local `source` path to its manifest path relative to the pinned upstream root. Those paths are provenance, not restore paths relative to `third_party/mattpocock`. Use the wrapper to refresh this catalog, not `skills experimental_install` against this stored lock.

`--check` performs a disposable local CLI installation of the vendored skills, compares all copied bytes, and compares the CLI-generated hashes with the stored lock. It does not implement a competing hash algorithm or access GitHub. `third_party/mattpocock/LICENSE` and `plugin.json` remain exact upstream bytes.

The npm CLI's experimental package sync was evaluated through its shipped documentation. It reconciles npm packages and package-declared remote sources, but does not replace this repository's upstream plugin-manifest selection rule. The stable `add` command plus a bounded reconciliation wrapper avoids adding an npm packaging layer for Matt's repository.

## Executed evidence

Verification used disposable roots under the configured scratch directory. The dependency toolchain was installed there with `npm ci --ignore-scripts`, not into a live agent environment.

- `npm view skills version engines dist.integrity repository --json` returned version `1.7.4`, Node `>=22.20.0`, and the first-party `vercel-labs/skills` repository.
- The installed package's `--help`, `docs/commands.md`, and `dist/cli.mjs` confirmed the exact flags, project-local lock format, copy exclusions, and hash ownership. The installed `--version` returned `1.7.4`.
- The registry lock for `skills@1.7.4` records `sha512-lHZJksE8UImNAr+LL6unqq7jERjdFw5EJasm17srycwL7rXHGdCmgu1L1ttLxUO9i3rdH+QQig+px0icHqLmRw==`.
- A real network fetch of Matt's commit `5beb35b040e3de97e54fa9e386d7e42d15c295c2`, followed by CLI installation, returned `{"files": 79, "revision": "5beb35b040e3de97e54fa9e386d7e42d15c295c2", "skills": 27, "status": "updated"}`.
- Repeating that isolated sync returned the same counts and `"status": "unchanged"`.
- A programmatic comparison confirmed all 79 CLI-installed skill files, the MIT license, and the plugin manifest match the repository baseline byte-for-byte. Only the lock representation changed.
- The 18 Matt regression tests passed using the real pinned npm CLI and explicitly synthetic upstream fixtures. They cover additions, updates, removals, excluded directories, unpublished same-name skills, malformed/empty selections, unexpected paths, failed fetches, CLI failures, omitted files, byte preservation, local-edit refusal, isolation, idempotence, and rollback.
- `python3 -m unittest discover -s tests -v` passed all 52 tests in the shared checkout, including the independently developed adaptation tests.
- Repository `--check` returned `{"files": 79, "revision": "5beb35b040e3de97e54fa9e386d7e42d15c295c2", "skills": 27, "status": "valid"}` while a PATH shim disabled Git and loaded a Node guard that throws on fetch, HTTP, HTTPS, TCP connection, and DNS lookup attempts. A negative-control fetch failed with `Offline proof: network access attempted`.
- `git diff --check` passed.

Both Matt workflows now install the locked dependency graph before testing. Their actions are pinned to first-party tag resolutions verified with `git ls-remote` and the pinned `action.yml` files. Checkout `d23441a48e516b6c34aea4fa41551a30e30af803`, setup-node `249970729cb0ef3589644e2896645e5dc5ba9c38`, and create-pull-request `5f6978faf089d4d20b00c7766989d076bb2fc7f1` use Node 24 internally. The sync/test runtime is separately pinned to Node 22.23.4.

## Limits

The host denied `unshare -n`, so the offline proof used the explicit Node API guard and disabled Git, not an OS network namespace. GitHub Actions have not been executed, and no PR, commit, push, or live agent installation was performed.

Local `--source` remains a trusted checkout or fixture interface. An explicitly supplied revision records the caller's assertion, not proof that modified checkout bytes came from that commit. Production automation uses the exact network fetch path.

CLI copy exclusions such as `metadata.json` can cause a future upstream refresh to fail. This is intentional: the wrapper will not discard upstream support files. Hash integrity follows the pinned CLI implementation. Replacement rollback handles ordinary process errors, not power loss or a forced kill between replacements. Staging and managed outputs must support filesystem renames; a cross-device rename fails safely instead of completing the update.

First-party references: [skills commands](https://github.com/vercel-labs/skills/blob/main/docs/commands.md), [skills package](https://www.npmjs.com/package/skills/v/1.7.4), and [pinned Matt source](https://github.com/mattpocock/skills/tree/5beb35b040e3de97e54fa9e386d7e42d15c295c2).
