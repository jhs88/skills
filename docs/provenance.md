# Sources

`sources.json` is the source manifest for all imported collections. It records repositories, pinned Git revisions, source paths or publication manifests, destinations, and update modes. Adapted sources list selected names and any per-skill revision overrides. `package-lock.json` pins the npm copying tool and its dependencies.

| Collection | Upstream | Update policy |
| --- | --- | --- |
| Matt Pocock | https://github.com/mattpocock/skills | Copy the published engineering/productivity manifest through npm skills |
| Tstack | https://github.com/t3dotgg/tstack | Read-only upstream comparison, manual reconciliation |
| Pstack | https://github.com/cursor/plugins/tree/main/pstack | Read-only comparison with per-skill baseline pins, manual reconciliation |

Git is the record of the imported files and maintained adaptations. Source revisions identify comparison baselines, not a claim that every adapted file matches upstream. The source manifest contains no per-file inventories or hashes.

Keep collection licenses and notices under `third_party/` when redistributing their files. These grants do not assign a license to original repository code or documentation.
