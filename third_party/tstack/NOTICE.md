# Tstack attribution

The nine skills under `skills/tstack/` are local working-tree adaptations of Theo Browne's [tstack](https://github.com/t3dotgg/tstack), pinned upstream at `7de017b3fc9d50c03cf3ecb98fb71e0ca65a78bd`. The complete MIT notice is in [LICENSE](LICENSE). Keep this directory with redistributed skill copies and their support files.

The immediate source was the repository owner's dirty Pi working tree, not an assertion that its HEAD contains these bytes. `adaptations.lock.json` records the Pi HEAD as context, the source file hashes, destination hashes, original upstream hashes, and source-document hashes. See `docs/adapted-imports.md` for the adaptation log and update procedure.

`scripts/pr-wait` is byte-identical to the pinned upstream helper. The two watcher reference documents and local integration instructions were taken from the Pi working tree. This import does not assign a new license to the owner's original additions. Their licensing remains pending owner approval. The upstream MIT notice applies to upstream material, not an inferred license grant for all repository content.

The read-only update checker and its offline tests are adaptations of Pi's `scripts/check_tstack_updates.py` and `tests/test_tstack_updates.py`. Their source hashes are recorded in `adaptations.lock.json`. No private runtime configuration or other Pi documentation is redistributed.
