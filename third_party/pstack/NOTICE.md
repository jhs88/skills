# Pstack attribution

The skills under `skills/pstack/` are local working-tree adaptations of Lauren Tan's [Pstack in cursor/plugins](https://github.com/cursor/plugins/tree/main/pstack):

- `technical-writing` is based on revision `bdf7aa355337897f167153e05069aca505dae17c`.
- `unslop` is based on revision `fd6dd6f7276956a532bb78a748a8d2818b6eb5f4`.

The complete upstream MIT notice is in [LICENSE](LICENSE). It was fetched from both exact revisions and verified identical to the Pi third-party notice. Keep this directory with redistributed skill copies.

The immediate source was the repository owner's dirty Pi working tree. `adaptations.lock.json` records the Pi HEAD only as context, with separate per-file hashes of the actual working-tree inputs and imported outputs. Do not claim the adaptations are byte-identical copies of upstream or committed Pi HEAD. Local additions retain their existing licensing posture; no new license for the owner's work is granted here.

`docs/adapted-imports.md` records the portable invocation wording change and the human reconciliation requirement. The collection-wide update inventory uses the `unslop` pin, with `technical-writing` explicitly overridden to its distinct pin. Other Pstack skills appear only as update-review candidates, not imported or discoverable skills.
