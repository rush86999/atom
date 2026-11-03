# Results — document freshness 9b6e01e90

| Scope | Result |
|---|---|
| Independent stale/current probe | **2 passed** |
| Focused backend suite | **188 passed** |
| SQL-new / index-old | refused |
| Missing index hash | refused |
| Identity / workspace / tenant mismatch | refused |
| Stale or revoked authority | refused |
| Matching SQL/index | verified, dependent readiness true |
| Stale extraction through executor/restart | dependent work not called; no completion |
| Valid file-read and matching upload twins | supported |
