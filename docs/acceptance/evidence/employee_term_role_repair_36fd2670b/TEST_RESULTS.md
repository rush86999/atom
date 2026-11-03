# Results — term role repair 36fd2670b

| Scope | Result |
|---|---|
| `test_verifier_terms_20f.py` | **2 passed** |
| Independent verifier probes | **22 passed** |
| Focused compiler/executor suite | **179 passed** |
| Affected backend suite | **789 passed**, 8 deselected |

The two previously reproduced defects now fail closed:

1. `tax_rate=0.07` selected as freight authority -> `WorkRequestCompileError`
   for semantic role mismatch.
2. Fact-backed freight valid at compile, expired before consumption ->
   `NeedsContext` from `quote.calculate`; executor leaves the step unapplied
   with no calculated value.

Valid twins for taught freight, tax none/rate/amount and zero freight still
compile; the deterministic two-domain campaign remains 4/4.
