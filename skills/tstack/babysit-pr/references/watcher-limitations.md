# Watcher limitations and independent verification

The executable `scripts/pr-wait` is preserved byte-for-byte from tstack
7de017b3fc9d50c03cf3ecb98fb71e0ca65a78bd. It is a read-only GitHub event helper,
not a merge authorization engine. It writes only its local lock and state under
`~/.local/state/pr-wait/`. Do not treat its stdout or exit code as a verdict.

## Known limitations at the pinned revision

- GraphQL reads the last 100 comments, reviews, and threads and the first 100
  replies per thread without pagination. Older unresolved findings can be absent.
- Greptile and Macroscope are hard-coded readiness bots. CodeRabbit is always
  advisory in the helper. Actual repository requirements can differ.
- Protection lookup errors are logged and may leave an empty required set.
  A 404 can mean inaccessible protection, not proof of no required checks.
- `green` accepts completed buckets other than failure/cancellation, including
  skipped checks. The repository, not the helper, decides accepted conclusions.
- Bot completion is not bot approval. A summary mentioning a short head SHA is
  a heuristic, not proof of a complete review tied to the exact commit.
- Unknown mergeability, draft status, human approvals, unresolved older threads,
  merge queues, and head/base changes across API reads need independent checks.
- No-check PRs do not automatically become green. The helper may keep waiting.
- Exit 0 also means already merged, not necessarily open and ready to merge.
- The helper has no wall-clock deadline. The owning process/scheduler must enforce
  the agreed limit and verify the watcher stopped. Default polling is 20 seconds;
  use the documented `--interval 60` or repository-appropriate backoff.

## Safe use

Read the complete current review and check state with paginated GitHub tools
before watching and again after each wake. Verify the exact head and base,
repository protection, expected review agents, required human approval, draft
status, and mergeability. If any required evidence is missing, report it as
unverified and do not merge. Apply `bot-triage.md` to every finding.

Use one watcher owner per PR. Foreground waits end with the session. A tracked
background process is not a verified durable monitoring service. Never promise
future notification without an authorized scheduler and verified destination.
