# Provenance

- First-party source: https://github.com/mattpocock/skills
- Initial pinned commit: `5beb35b040e3de97e54fa9e386d7e42d15c295c2`.
- Selection authority: `.claude-plugin/plugin.json`, explicit `skills` array only.
- Allowed layout: `skills/engineering/<slug>` and `skills/productivity/<slug>`.
- Destination: `skills/mattpocock/<slug>/`, complete support files without content changes.
- License: upstream MIT, copyright 2026 Matt Pocock. Exact source notice is preserved in `third_party/mattpocock/LICENSE`.
- Current provenance: `upstreams.lock.json`. CLI-generated content hashes and normalized source paths live in `third_party/mattpocock/skills-lock.json`. See `docs/npm-skills-verification.md` for the pinned npm installer and current workflow action pins.

The manifest itself is preserved byte-for-byte as `third_party/mattpocock/plugin.json`. The lock changes only with synchronized provenance or content; it has no wall-clock timestamp. Offline validation checks internal consistency and hashes, not upstream authenticity. The normal network sync checks out the pinned upstream commit. Local `--source` mode trusts the caller's asserted revision and checkout contents.

The initial baseline used these action pins, since superseded in the Matt workflows by the Node-24 actions documented in `docs/npm-skills-verification.md`:

- `actions/checkout@11d5960a326750d5838078e36cf38b85af677262`, the `v4` ref, resolves to the commit described as `backport fixes to releases-v4 (#2524)`.
- `peter-evans/create-pull-request@22a9089034f40e5a961c8808d113e2c98fb63676`, the `v7` ref, resolves to the commit described as `fix: restrict remote prune to self-hosted runners (#4250)`.

New revisions can add, change, or delete published skills. Unexpected layouts fail closed for owner review. MIT-like license changes are copied with the update and must be reviewed in the PR. This file records the initial baseline; the lock is authoritative for later updates.

Tstack and Pstack are separately tracked adaptations from the Pi working tree, not unchanged mirrors. Their exact input/output hashes, upstream revisions, and collection baselines are recorded in `adaptations.lock.json`, with MIT notices under `third_party/tstack/` and `third_party/pstack/`. See `docs/adapted-imports.md`. Uncle Bob's pipeline is excluded.

No root license was chosen for the owner's original scripts and docs. Their licensing remains pending owner approval. Do not infer an MIT grant for those files from the third-party notice.
