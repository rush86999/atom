# Results — extraction identity 637a6e178

| Scope | Result |
|---|---|
| Independent current-ev4 eligibility probe | passed |
| Independent old-ev3 rejection probe | passed |
| Original stale/current freshness probe | passed |
| Focused producer/consumer/executor suite | **193 passed** |
| Current versioned SQL/index/binding | eligible, exact ev4 identity |
| Old extractor / malformed / unequal / mixed kind | refused |
| Bare supported upload revision | exact match accepted |
| Stale extraction through executor/restart | dependent work not called |
