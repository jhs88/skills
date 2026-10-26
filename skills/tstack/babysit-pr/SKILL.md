---
name: babysit-pr
description: Use to babysit a PR and fix review or CI findings.
---

# Babysit PR

Many repos have AI review bots. They're helpful, even if they are not always
right.

## Waiting

Never write your own watcher, polling loop, or `sleep` loop. Use exactly one
watcher per PR: native T3 watching when those tools are exposed, otherwise
`pr-wait`. Never run both. Only the parent that owns the PR watches it; review
children must not start watchers. Reuse an existing watch rather than duplicating it.

### Native T3 watching

When `watch_pull_request` is available, handle current findings, register the
PR URL, and confirm `watching: true` or reuse an existing watch. Re-read the PR
after registration to catch races, then end the turn with the watch active.
T3 wakes the thread on changes; a notification is news, not a merge decision.
On a wake, re-read the current head/base, checks, and reviews before acting.
Do not also start a script or polling process. If registration fails, report
the blocker instead of silently switching watchers.

At final handoff, a question, or completion, call `unwatch_pull_request` and
verify `watching: false`. Report cleanup failures. Ending a turn while awaiting
a T3 wake is not a final handoff. Native watching does not enforce a hard deadline.

### Script fallback: `pr-wait`

Wait with `scripts/pr-wait` from this skill's directory (use its absolute
path).

```bash
python3 <absolute-skill-dir>/scripts/pr-wait <pr> [--repo owner/name] [--until ready|green|any-change]
```

It prints one line per real event. It exits 0 when the `--until` condition is
met or the PR merges, 1 when it needs you (a required check failed, conflicts,
unresolved threads, PR closed), and 2 on bad input.

- `ready` (default): required checks green, Greptile or Macroscope reviewed the
  head, and no unresolved threads. Use this to babysit.
- `green`: required checks only. Use it when the repo has no Greptile or
  Macroscope.
- `any-change`: exit on the first event.

Use the available tracked process/notification facility, or run it as one long
command with an appropriate timeout. It ends on its own. Do not promise later
wakeups unless the runtime actually supports and has armed them.

Start it again after you push, after you handle an exit 1, and after a resume.
It remembers what it already reported, so nothing that arrived in between is
lost. If it says another pid already watches the PR, do not start a second one.
Kill the old one only if its events do not reach you.

With the watcher: when an event needs no action, end your turn without a
message. Never post or say "still waiting".

## GitHub rate limits

`gh pr create`, `gh pr view`, and `gh pr checks` use GraphQL. When GraphQL is
used up, the REST limit is separate and usually still has room. Use
`gh api repos/<owner>/<repo>/pulls/<n>` to read a PR, and
`gh api repos/<owner>/<repo>/commits/<sha>/check-runs` for checks.

## Reviews

Only act on checks and comments newer than the latest push. Verify every bot
finding against the source before changing code. Fix real findings and CI
failures, distinguish repository failures from infrastructure flakes, and reply
with a written reason when dismissing false positives.

If the repo has `.macroscope/check-run-agents/*.md`, read those rules before you
reply to a Macroscope finding. Its findings cite them.

CodeRabbit is advisory. Treat its findings like any other finding, but never
wait for it and never hold a merge for it.

If a review bot leaves feedback you believe is not worth addressing, reply with
a written reason and resolve the comment. Use the `leaving-pr-comments` skill
for every comment posted on the user's behalf.

Screenshots and videos help as well, when you have a way to upload them.

Keep the PR at the size the user's goal needs. Review loops tend to grow a
PR one cheap-looking fix at a time. Fix real bugs in the intended case.
Decline the rest with a written reason, and list them as follow-ups:
unneeded tests, guards for edge cases that do not matter, extra integration
or compatibility, and small performance costs. Prefer the fix that deletes or
narrows code.

## Base branch and merging

Keep an eye on changes to `main` and rebase when needed. `pr-wait` reports when
new base commits touch this PR's files, and when the PR becomes BEHIND or DIRTY.
Check for BEHIND yourself before you call the PR ready.
If an overlapping PR makes this one obsolete, stop monitoring, report it to the
user, and ask before closing the PR unless closure was explicitly authorized.

If nothing has changed, stay quiet rather than posting filler comments. Stop when `pr-wait` exits 0, then independently check the live merge gate on
the latest head. An exit 0 can also mean the PR already merged. Merge only when the user explicitly requested it;
otherwise report that the PR is ready. Right before a merge, run `git fetch` and
check the PR again. Never merge when it is BEHIND or DIRTY, or when base commits
that landed after the last green run touch this PR's files. Rebase, push, and
wait for green again.

The watcher is an event helper, not the merge decision. Its pinned code uses
limited review windows and bot heuristics. Read complete paginated evidence
when assessing the gate. See `references/watcher-limitations.md`.

## Local integration

Follow the requested workflow directly. Full-send is end-to-end authorization
for this task, not a reason to request approval again at every child skill.
Full-stop includes the same preparation but never merging. Runtime/system
approval prompts still apply. Use native tools that actually exist and verify
remote writes by reading back their exact targets. Main is the default branch.
