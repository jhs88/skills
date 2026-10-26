---
name: leaving-pr-comments
description: Use when posting agent-authored GitHub PR comments.
---

# Leaving PR Comments

Prefix every agent-authored comment left on the user's behalf with this GitHub
note callout:

```md
> [!NOTE]
> 🤖 **<model> responding on behalf of <user>**

Actual comment starts here.
```

Use the verified public name of the model that wrote the comment, and the
user's name or GitHub login.

If the harness does not expose a model name, use the harness name. Do not guess.

Before posting, check the entire comment, including quoted text and
attachments, for secrets and private details.

Keep the attribution inside the note and the actual reply outside it. The
context line must start with the robot emoji. Do not add a horizontal rule,
Setext underline, heading, signature footer, or a second attribution.

Apply this format to top-level PR comments, inline review comments, replies to
bots or reviewers, and written explanations used before resolving or
dismissing feedback. Do not add it to PR descriptions, commit messages, or text
the user explicitly asked to post verbatim without attribution.

Write the comment itself in a direct style:

- Lead with the conclusion.
- Cite the relevant code, behavior, check, or reproduction.
- Keep it concise and avoid filler, canned thanks, or status narration.
- Distinguish verified facts from judgment.

Preview the final Markdown before posting so quoting and blank lines render as
shown. After posting, record the URL and read back the exact comment or review to
verify the body and target.
Resolve a review thread only after its response was posted successfully.

## Local integration

Follow the requested workflow directly. Full-send is end-to-end authorization
for this task, not a reason to request approval again at every child skill.
Full-stop includes the same preparation but never merging. Runtime/system
approval prompts still apply. Use native tools that actually exist and verify
remote writes by reading back their exact targets. Main is the default branch.
