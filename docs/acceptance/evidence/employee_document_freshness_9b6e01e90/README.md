# Indexed document freshness repair — source 9b6e01e90

`document.text` now requires the indexed extraction receipt and the scoped
authoritative `IngestedDocument` row to agree on:

- resource/document identity;
- workspace and tenant scope;
- source content hash/version;
- expected binding version; and
- current freshness state.

A newer SQL version can no longer relabel stale cached text. Missing,
contradictory, out-of-scope or stale extractions refuse with a typed
missing/stale result, keeping dependent calculations/artifacts blocked. The
result records the actual indexed source version and a separate extracted-text
hash; binary source hashes are not compared to text hashes.

Upload producers now store the same source hash in indexed metadata and the
SQL row, so new valid uploads retain their matching-version positive behavior.
