---
name: council
description: Use when asked for a three-model GPT council review.
---

# Council

Bring in three independent delegates to help with the user's request, usually
for review or feedback, at high reasoning effort. Use the GPT subscription
through the existing connection. The default roster is:

- `gpt-6.1-sol`
- `gpt-6-astra`
- `gpt-6-luna`

Discover these models through the runtime's existing configured GPT
subscription connection. Three providers are not required. If the user names other GPT council members, use
those instead. Keep each delegate in a fresh context.

Use the runtime's advertised model discovery and native subagent tools.
Verify the selected model IDs and inspect actual schemas; do not invent fields
or call T3-only APIs. Run one delegate per model in parallel when supported.
If a named member or per-child model selection is unavailable, report it
instead of substituting. Do not add non-GPT models, new subscriptions, or
provider configuration. Delegates must not start further delegates.

Give each delegate the request and relevant context. For review or feedback,
keep their work read-only. Collect their responses and summarize the useful
findings, disagreements, and recommended next steps.

For a code review, ask each delegate for a score out of 10.
Count each full review pass as one round.
A fresh review after fixes starts a new round.

If the work ends in a pull request, put the results in the PR description.
Put this section before the model and harness line at the end:

```markdown
## Council review

Rounds: 2

| Delegate | Round 1 | Round 2 |
| --- | --- | --- |
| gpt-6.1-sol | 7/10 | 9/10 |
| gpt-6-astra | 8/10 | 10/10 |
| gpt-6-luna | 7/10 | 9/10 |
```

If a delegate gives no score, write `no score`. Do not invent one.
If the PR is open, edit the description. Do not post a comment for this.
If there is no PR, put the same results in the final reply only.

If you agree with their recommendations, make the changes and request a fresh
review after. Continue this process until all delegates are satisfied with the
outcome.

Do not let repeated reviews result in scope creep. It is your job to fight to
keep scope limited.

## Local integration

Follow the requested workflow directly. Full-send is end-to-end authorization
for this task, not a reason to request approval again at every child skill.
Full-stop includes the same preparation but never merging. Runtime/system
approval prompts still apply. Use native tools that actually exist and verify
remote writes by reading back their exact targets. Main is the default branch.
