# Verification contract

From the repository root:

```sh
python3 -m unittest discover -s tests -v
python3 scripts/sync_mattpocock.py --check
```

The public seam under test is synchronization from a local source fixture plus the CLI and read-only validation. Tests cover additions, byte-preserving updates, removals, unlisted/experimental exclusion, malformed and empty manifests, invalid paths, duplicate names, missing files/license, symlink rejection, local modification protection, fetch failure, rollback after an injected installation error, CLI source mode, and same-revision idempotence including file times. Fixtures stay in the configured temporary directory.

A real baseline proof also runs the network sync twice at the same full revision and asserts the second result is `unchanged`, then checks every managed file against the lock. No upstream support code is executed. Workflow jobs run these commands but their GitHub execution is unverified until publication and enablement.

## Initial baseline results

- `python3 -m unittest discover -s tests -v`: 13 tests passed.
- Real network sync at `5beb35b040e3de97e54fa9e386d7e42d15c295c2`: 27 skills and 79 files copied, including 52 support files. Subsequent automatic-HEAD and pinned-revision syncs both returned `unchanged`.
- Offline validation returned `valid` at that revision.
- Independent comparison against GitHub's complete Git tree found exactly the selected 79 files, with every byte matching the upstream Git blob SHA. The license and saved manifest also matched their upstream blobs.
- Both workflow YAML files parsed successfully and all action references use full commit pins verified through the GitHub API. Actual GitHub workflow execution is not yet tested.
- Four apparently missing relative Markdown links are upstream example placeholders, three glossary example paths and a wayfinder ticket-link placeholder. No selected source files are absent.
- A protected-file approval hook blocked creation of root `AGENTS.md` after its prompt timed out. It was not retried or bypassed. The requested root agent-instruction file is therefore still missing and needs explicit approval.
- No commits, remote writes, remote labels, or live agent installations were performed.

Do not describe this as a live agent installation test. Runtime discovery, model behavior, support-script execution, and cross-runtime compatibility are not covered. There is no live configuration to clean up; temporary clone, fixture, and staging directories are owned and cleaned by their respective Python context managers. Interrupted multi-path installations require inspection before resuming.
